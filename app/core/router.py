import time
import logging
import json
import re
import httpx
import asyncio
from typing import Any, List, Dict, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.metrics import metrics
from app.core.llm import invoke_with_retry
from app.models.models import User, APIUsage, Course, Topic
from sqlalchemy import func
from app.core.cache import course_cache, topic_cache
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

class AIRouter:
    """
    Centralized AI Routing System for CourseForge.
    Handles multi-provider strategies, fallbacks, quality checks, and metrics.
    """
    
    # Models to use for Hugging Face
    HF_TEXT_MODEL = "Qwen/Qwen2.5-7B-Instruct"

    # Distributed circuit breaker state is now in Redis
    # Keys: cb:{provider}:failures, cb:{provider}:frozen_until
    
    @staticmethod
    async def get_user_stage(db: Session, user_id: int) -> str:
        """Determines the user's stage based on generation count."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "new"
        
        count = user.generation_count
        if count == 0:
            return "new"      # Course 1: Full Gemini
        elif count == 1:
            return "hybrid"   # Course 2: Hybrid
        else:
            return "established" # Course 3+: HF Default
            
    @staticmethod
    def _check_quality(text: str) -> bool:
        """
        Validates the output for structural integrity.
        Checks for length, headings, and examples.
        """
        if not text or len(text) < 300:
            return False
            
        # Check for markdown headings
        if not re.search(r"##?\s+", text):
            return False
            
        # Check for examples/analogies/lists
        if not any(marker in text.lower() for marker in ["example:", "analogy:", "1.", "- "]):
            return False
            
        return True

    @classmethod
    async def generate_text(
        cls, 
        db: Session,
        prompt: str, 
        user_id: Optional[int] = None,
        system_instruction: Optional[str] = None,
        provider_preference: Optional[str] = None, # Force 'gemini' or 'huggingface'
        require_json: bool = False,
        use_cache: bool = True,
        cache_key: Optional[str] = None
    ) -> str:
        start_time = time.perf_counter()
        
        # 0. Cache Logic (L1/L2 SWR)
        if use_cache and cache_key:
            cache_instance = cls._get_cache_for_prompt(prompt)
            if cache_instance:
                # SWR: Returns value if hit (even if stale), triggers background refresh
                cached_data = await cache_instance.get(
                    cache_key, 
                    revalidate_func=cls.generate_text, # Recursive call for revalidation
                    db=db,
                    prompt=prompt,
                    user_id=user_id,
                    system_instruction=system_instruction,
                    provider_preference=provider_preference,
                    require_json=require_json,
                    use_cache=False # Crucial: prevent infinite loop
                )
                if cached_data:
                    cls._log_usage(db, user_id, "cache", "generate_text", 0, "cache_hit")
                    return cached_data

        provider = provider_preference
        
        # 1. Determine Strategy if no preference is forced
        if not provider and user_id:
            stage = await cls.get_user_stage(db, user_id)
            
            # Quota Check (Soft Limit 80%)
            gemini_usage_today = db.query(func.count(APIUsage.id)).filter(
                APIUsage.provider == "gemini",
                APIUsage.timestamp > datetime.now() - timedelta(days=1)
            ).scalar()
            
            # Assume a soft limit of 100 requests/day for Gemini Flash (adjust as needed)
            if gemini_usage_today > 80:
                provider = "huggingface"
            elif stage == "new":
                provider = "gemini"
            elif stage == "hybrid":
                # For hybrid, we alternate or use complexity heuristic
                # Here: syllabus generation (if contains 'course outline') uses Gemini
                if "syllabus" in prompt.lower() or "structure" in prompt.lower():
                    provider = "gemini"
                else:
                    provider = "huggingface"
            else:
                provider = "huggingface"
        else:
            provider = provider or "gemini" # Default fallback for system tasks

        # 1.5 Rate Limiting (Redis-based)
        if user_id:
            now_ts = time.time()
            rl_key = f"rl:{user_id}"
            if redis_client:
                try:
                    pipe = redis_client.pipeline()
                    pipe.zremrangebyscore(rl_key, 0, now_ts - 60)
                    pipe.zcard(rl_key)
                    pipe.zadd(rl_key, {str(now_ts): now_ts})
                    pipe.expire(rl_key, 60)
                    results = pipe.execute()
                    
                    count = results[1]
                    if count >= 5: # 5 requests per minute
                        logger.warning(f"User {user_id} is rate limited.")
                        # Raising standard fallback exception to propagate HTTP 429
                        from fastapi import HTTPException
                        raise HTTPException(status_code=429, detail="Too many generation requests. Please wait a minute and try again.")
                except ImportError:
                    pass # HTTPException might not be explicitly imported globally
                except Exception as e:
                    if "429" in str(e):
                        raise e
                    logger.error(f"[REDIS_ERROR] Rate limiter failure: {e}. Failing open.")
            else:
                logger.warning("[REDIS_OFFLINE] Rate limiting skipped. Redis unavailable.")

        # 2. Execute with Fallback Depth and Retries
        MAX_TOTAL_ATTEMPTS = 5
        total_attempts = 0
        response = None
        success = False
        final_provider = provider
        
        providers_to_try = [provider]
        if provider == "huggingface": providers_to_try.append("gemini")
        elif provider == "gemini": providers_to_try.append("huggingface")

        for current_provider in providers_to_try:
            if total_attempts >= MAX_TOTAL_ATTEMPTS:
                break

            now = time.time()
            
            # Check Redis for circuit breaker state
            frozen_until = 0
            if redis_client:
                try:
                    frozen_until = float(redis_client.get(f"cb:{current_provider}:frozen_until") or 0)
                except Exception as e:
                    logger.error(f"[REDIS_ERROR] Circuit breaker read failed: {e}. Failing open.")

            if frozen_until > now:
                logger.warning(f"Provider {current_provider} is on cooldown.")
                continue
            
            try:
                metrics.record_request()
                total_attempts += 1
                
                response = await asyncio.wait_for(
                    cls._invoke_provider(current_provider, prompt, system_instruction, require_json),
                    timeout=60.0 
                )
                
                # Success: Reset failures in Redis
                if redis_client:
                    redis_client.delete(f"cb:{current_provider}:failures")
                
                # Handle Degraded Structure (Step 4 integration)
                if isinstance(response, dict) and response.get("status") == "degraded":
                    logger.warning(f"[ROUTER_DEGRADED] Provider {current_provider} returned degraded response.")
                    if current_provider == "gemini":
                         # Gemini failure counts towards total attempts
                         continue
                
                # 3.2 Post-Processing & Quality Check
                if require_json and isinstance(response, str):
                    try:
                        json.loads(response)
                    except:
                        logger.warning(f"Provider {current_provider} returned invalid JSON.")
                        continue # Try next provider
                
                success = True
                final_provider = current_provider
                break
                
            except Exception as e:
                logger.error(f"[ROUTER_FALLBACK] provider={current_provider} error=\"{str(e)[:50]}\"")
                metrics.record_failure(fallback=True)
                
                if redis_client:
                    redis_client.incr(f"cb:{current_provider}:failures")
                    redis_client.expire(f"cb:{current_provider}:failures", 600)
                    
                    failures = int(redis_client.get(f"cb:{current_provider}:failures") or 0)
                    if failures >= 3:
                        redis_client.setex(f"cb:{current_provider}:frozen_until", 120, str(time.time() + 120))
        
        if not success:
            logger.critical(f"[SYSTEM_FAILSOFT] All AI providers exhausted after {total_attempts} attempts.")
            response = cls._get_static_fallback(prompt, require_json)
            final_provider = "static_fallback"

        # 5. SUMMARY LOGGING (ULTIMATE)
        latency = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"[REQUEST_SUMMARY] attempts={total_attempts} final_provider={final_provider} status={'success' if success else 'degraded'} latency={latency}ms")
        
        cls._log_usage(db, user_id, final_provider, "generate_text", latency, "success" if success else "fallback")
        return response

    @classmethod
    async def _invoke_provider(cls, provider: str, prompt: str, system: str = None, require_json: bool = False) -> str:
        if provider == "gemini":
            mime = "application/json" if require_json else None
            return await asyncio.to_thread(
                invoke_with_retry, 
                prompt, 
                system_instruction=system, 
                response_mime_type=mime
            )
        
        elif provider == "huggingface":
            return await cls._invoke_huggingface(prompt, system)
            
        raise ValueError(f"Unknown provider: {provider}")

    @classmethod
    async def _invoke_huggingface(cls, prompt: str, system: str = None) -> str:
        """Calls Hugging Face Inference API."""
        if not settings.HF_API_KEY:
            raise ValueError("HF_API_KEY not configured")
            
        from huggingface_hub import AsyncInferenceClient
        client = AsyncInferenceClient(token=settings.HF_API_KEY)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await client.chat_completion(
                messages=messages,
                model=cls.HF_TEXT_MODEL,
                max_tokens=4000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"HF API Error: {str(e)}")

    @classmethod
    def _get_static_fallback(cls, prompt: str, require_json: bool = False) -> str:
        """Returns high-quality static templates when all APIs fail."""
        # Enhanced topic extraction from prompt
        topic_match = re.search(r"(?:topic|subject|teach):\s*([^\n,.]+)", prompt, re.I)
        topic = topic_match.group(1).strip() if topic_match else "this subject"
        
        # Clean up common prefixes if they were caught in the match
        for prefix in ["to teach", "about"]:
            if topic.lower().startswith(prefix):
                topic = topic[len(prefix):].strip()
        
        if require_json:
            # Check if it's a syllabus request or a topic content request
            prompt_lc = prompt.lower()
            is_coding = any(kw in topic.lower() for kw in ["java", "python", "javascript", "code", "programming", "c++", "rust", "react"])
            
            if "syllabus" in prompt_lc or "curriculum" in prompt_lc:
                if is_coding:
                    return json.dumps({
                        "title": f"Mastery of {topic}",
                        "description": f"A comprehensive roadmap to mastering {topic}, synthesized from core pedagogical principles.",
                        "modules": [
                            {"title": "Module 1: Foundations", "description": "Core concepts and setup.", "lessons": [{"title": "Getting Started with " + topic, "summary": "Setting the baseline."}]},
                            {"title": "Module 2: Logic & Flow", "description": "Mastering logical control.", "lessons": [{"title": "Control Structures", "summary": "Loops and conditionals."}]},
                            {"title": "Module 3: Data Architectures", "description": "How data is organized.", "lessons": [{"title": "Data Management", "summary": "Storing information."}]},
                            {"title": "Module 4: Functional Design", "description": "Reusable logic nodes.", "lessons": [{"title": "Functions & Methods", "summary": "Abstraction layers."}]},
                            {"title": "Module 5: System Objects", "description": "Advanced blueprinting.", "lessons": [{"title": "Object Orientation", "summary": "Real-world modeling."}]},
                            {"title": "Module 6: Resilient Logic", "description": "Error handling and recovery.", "lessons": [{"title": "Exceptions", "summary": "Managing failures."}]},
                            {"title": "Module 7: Integration Nodes", "description": "Connecting to the grid.", "lessons": [{"title": "API & Exterior Logic", "summary": "External communication."}]},
                            {"title": "Module 8: Final Synthesis", "description": "End-to-end implementation.", "lessons": [{"title": "Capstone Implementation", "summary": "Final project."}]}
                        ]
                    })
                return json.dumps({
                    "title": topic,
                    "description": f"Foundational curriculum for {topic}.",
                    "modules": [
                        {"title": "Module 1: Foundations", "description": "Basic principles.", "lessons": [{"title": "Introduction to " + topic, "summary": "Baseline overview."}]},
                        {"title": "Module 2: Core Mechanisms", "description": "How it works.", "lessons": [{"title": "Inner Workings", "summary": "Deep dive."}]},
                        {"title": "Module 3: Mastery Synthesis", "description": "Final convergence.", "lessons": [{"title": "Advanced Insights", "summary": "Expert level."}]}
                    ]
                })
            else:
                fallback_text = f"### Overview of {topic}\n\n{topic} represents a fundamental node in the current learning architecture. By synthesizing its core principles, we can bridge the gap between theoretical understanding and practical implementation. This lesson focuses on the first principles that allow {topic} to function as a resilient component in modern systems.\n\n#### Key Principles\n1. **Atomic Logic**: Breaking down {topic} into its smallest components.\n2. **Synthesis**: Reconnecting these components to form a coherent whole.\n3. **Practical Application**: Applying this logic to real-world scenarios to ensure mastery and retention of the subject matter."
                return json.dumps({
                    "beginner_content": fallback_text,
                    "intermediate_content": fallback_text + "\n\n*Note: This synthesis is running in Neural Cache mode. Master-grade AI synthesis will resume upon grid stabilization.*",
                    "expert_content": fallback_text + "\n\n**Architectural Node**: Advanced implementation details are being indexed.",
                    "examples": [f"Standard application of {topic} in production."],
                    "analogies": [f"Thinking of {topic} like a key component in a vast network."],
                    "takeaways": ["Understand first principles", "Develop modular logic"],
                    "summary": f"A baseline synthesis of {topic} for immediate study.",
                    "code": [f"// Standard Implementation for {topic}\n// Neural Grid Mode active"],
                    "quizzes": [],
                    "flashcards": []
                })

        return f"""
# Introduction to {topic}

Welcome to this course on {topic}. Unfortunately, our real-time AI generation is undergoing maintenance, but we have prepared this foundational structure for you.

## Core Concepts
- **Definition**: Understanding the first principles of {topic}.
- **Importance**: Why mastering this subject is critical in today's landscape.
- **Application**: How to apply these nodes of knowledge in real-world scenarios.

## Learning Path
1. **Foundations**: Building the baseline understanding.
2. **Intermediate Synthesis**: Connecting the dots between complex variables.
3. **Expert Forge**: Mastering the edge cases and advanced implementation.

*Note: Please refresh the page in a few moments to witness the full AI-generated curriculum.*
"""

    @staticmethod
    def _get_cache_for_prompt(prompt: str) -> Optional[Any]:
        """Heuristic to decide which cache instance to use."""
        prompt_lc = prompt.lower()
        if "syllabus" in prompt_lc or "curriculum" in prompt_lc:
            return course_cache
        elif "topic" in prompt_lc or "lesson" in prompt_lc:
            return topic_cache
        return None

    @staticmethod
    def _log_usage(db: Session, user_id: Optional[int], provider: str, action: str, latency: int, status: str):
        try:
            usage = APIUsage(
                user_id=user_id,
                provider=provider,
                action=action,
                latency_ms=latency,
                status=status
            )
            db.add(usage)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log API usage: {e}")
            db.rollback()
