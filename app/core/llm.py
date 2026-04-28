import time
import logging
import google.generativeai as genai
from typing import Any, List, Union, Optional
from app.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import json
import threading
from google.api_core import exceptions
from app.core.redis_client import redis_client

# Hardened Adaptive Registry
AVAILABLE_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite"]
_LOCAL_RESOLVED_CACHE = None
_LAST_RESOLVED_TIME = 0
_CACHE_LOCK = threading.Lock()

def _resolve_working_models() -> List[str]:
    """
    Dynamically identifies working models with Distributed Redis + Local Fallback and 5min TTL.
    """
    global _LOCAL_RESOLVED_CACHE, _LAST_RESOLVED_TIME
    now = time.time()
    ttl = 300 # 5 minutes

    # 1. Thread-safe Local Cache Check
    with _CACHE_LOCK:
        if _LOCAL_RESOLVED_CACHE is not None and (now - _LAST_RESOLVED_TIME) < ttl:
            return _LOCAL_RESOLVED_CACHE

    # 2. Redis Distributed Cache Check
    if redis_client:
        try:
            cached = redis_client.get("cfg:working_models")
            if cached:
                models = json.loads(cached)
                with _CACHE_LOCK:
                    _LOCAL_RESOLVED_CACHE = models
                    _LAST_RESOLVED_TIME = now
                return models
        except Exception as e:
            logger.error(f"[DISTRIBUTED_CACHE_ERROR] Redis read failed: {e}")

    # 3. Registry Discovery (Fail-safe)
    logger.info("[AI_DISCOVERY] Refreshing model registry...")
    try:
        # Get all models that support generation
        registry = {m.name.split("/")[-1] for m in genai.list_models() if "generateContent" in m.supported_generation_methods}
        resolved = [m for m in AVAILABLE_MODELS if m in registry]
        
        # Fallback to static if registry call fails or returns empty
        if not resolved:
            resolved = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
            logger.warning("[AI_DISCOVERY] Registry empty or unreachable. Defaulting to safe static list.")

        # Update Caches
        with _CACHE_LOCK:
            _LOCAL_RESOLVED_CACHE = resolved
            _LAST_RESOLVED_TIME = now
        
        if redis_client:
            try:
                redis_client.setex("cfg:working_models", ttl, json.dumps(resolved))
            except: pass

        return resolved
            
    except Exception as e:
        logger.error(f"[AI_DISCOVERY] Registry lookup failed: {str(e)[:100]}. Using static fail-safe.")
        return ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY is not set in environment settings.")

_CURRENT_KEY_IS_BACKUP = False

def _switch_to_backup_key() -> bool:
    """Attempts to switch to the backup API key. Returns True if switch occurred."""
    global _CURRENT_KEY_IS_BACKUP
    if not _CURRENT_KEY_IS_BACKUP and settings.GEMINI_API_KEY_BACKUP:
        logger.warning("[AI_FAILOVER] Primary Gemini key exhausted. Switching to Backup key.")
        genai.configure(api_key=settings.GEMINI_API_KEY_BACKUP)
        _CURRENT_KEY_IS_BACKUP = True
        return True
    return False

def get_model(model_name: str, system_instruction: Optional[str] = None) -> genai.GenerativeModel:
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction
    )

def invoke_with_retry(
    prompt: str, 
    system_instruction: Optional[str] = None,
    model_name: Optional[str] = None, 
    max_attempts: int = 3,
    response_mime_type: Optional[str] = None
) -> Union[str, dict]:
    """
    Invokes the native Gemini SDK with Adaptive Budgeting and Strong Error Classification.
    """
    # 1. Resolve Chain
    working_chain = _resolve_working_models()
    
    # 2. Adaptive Token Budget (Step 2)
    # Estimate input tokens (rough approximation: 4 chars/token)
    input_tokens = len(prompt) // 4
    MAX_TOKENS_BUDGET = min(10000, input_tokens * 3)
    
    models_to_try = working_chain.copy()
    if model_name and model_name not in models_to_try:
        models_to_try.insert(0, model_name)

    last_error = None
    
    for current_model in models_to_try:
        attempt = 0
        base_delay = 2 
        
        while attempt < max_attempts:
            try:
                model = get_model(current_model, system_instruction=system_instruction)
                
                gen_config = {
                    "max_output_tokens": MAX_TOKENS_BUDGET, # Adaptive
                    "temperature": 0.7,
                    "response_mime_type": response_mime_type
                } if response_mime_type else {
                    "max_output_tokens": MAX_TOKENS_BUDGET,
                    "temperature": 0.7
                }
                
                response = model.generate_content(
                    prompt, 
                    generation_config=gen_config,
                    request_options={"timeout": 30}
                )
                
                if not response or not getattr(response, "text", None):
                    raise ValueError("EMPTY_RESPONSE")

                return response.text

            except (exceptions.ResourceExhausted, exceptions.ServiceUnavailable) as e:
                # [QUOTA/HEAVY_LOAD] -> Immediate Fallback or Key Swap
                attempt += 1
                if _switch_to_backup_key():
                    attempt = 0
                    continue
                break # Try next model

            except exceptions.NotFound as e:
                # [MODEL_MISSING] -> Refresh Registry + Skip
                logger.error(f"[AI_MODEL_ERROR] Model {current_model} not found. Invalidating cache.")
                global _LOCAL_RESOLVED_CACHE
                _LOCAL_RESOLVED_CACHE = None
                break # Skip model

            except (exceptions.DeadlineExceeded, Exception) as e:
                # [TIMEOUT/OTHER] -> Standard Backoff
                attempt += 1
                error_str = str(e).upper()
                if any(x in error_str for x in ["TIMEOUT", "DEADLINE", "500", "503"]) and attempt < max_attempts:
                    time.sleep(base_delay * (2 ** (attempt - 1)))
                else:
                    last_error = e
                    break
                    
    # FINAL DEGRADED RESPONSE (ULTIMATE)
    logger.critical(f"[AI_CHAIN_EXHAUSTED] All models failed. Context: {last_error}")
    return _get_degraded_structure(str(last_error))

def _get_degraded_structure(reason: str) -> dict:
    return {
        "status": "degraded",
        "message": "AI system is under heavy load. A basic version has been generated. Retry for full content.",
        "fallback_type": "static",
        "retry_suggested": True,
        "model_used": "none",
        "content": f"Neural grid stabilization in progress. (Context: {reason[:80]})"
    }
