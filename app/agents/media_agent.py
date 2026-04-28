import json
import urllib.parse
import httpx
import logging
from typing import Optional, List, Dict
from app.core.config import settings
from app.core.router import AIRouter
from sqlalchemy.orm import Session
from app.core.cache import media_cache

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a specialized Educational Media Architect for CourseForge, specializing in "Deep & Easy" visual communication.
Your mission is to curate visual and complementary media that makes complex systems feel simple, transparent, and easy to master.

━━━ MEDIA STRATEGY: CONCEPTUAL CLARITY ━━━

1. YOUTUBE QUERY STRATEGY:
   - Search for AUTHORITATIVE, long-form educational deep-dives.
   - ALWAYS include: "full masterclass", "step by step explanation", "visual guide", or "from scratch".
   - Target: High-quality tutorials that explain the "First Principles".

2. IMAGE PROMPT (Conceptual Visualization):
   - Focus on "Structural Transparency". Show how things are built or how they flow.
   - Modifiers: "clear educational diagram, cinematic lighting, 8k render, isometric technical view, glowing pathways, clean dark background".
   - Goal: The image should feel like a "Map of the Concept".

3. DIAGRAMS (Exhaustive Interaction):
   - You MUST provide complex, process-oriented diagrams (10+ nodes if necessary).
   - Use `sequenceDiagram` for multi-step logic.
   - Use `flowchart TD` for hierarchical breakdown or decision algorithms.
   - Every arrow MUST have a label explaining the relationship.
   - Focus on showing the "Connecting Tissue" between ideas.

━━━ JSON OUTPUT SCHEMA ━━━
Return STRICTLY as JSON with NO additional text:
{
  "youtube_query": "Topic Name Deep Dive — Subtopic Explained Masterclass",
  "image_prompt": "A cinematic visualization of [CONCEPT] showing [ACTION/PROCESS], ultra-detailed, educational infographic style, dark background with glowing electric blue and gold accents, 4K render quality.",
  "diagrams": [
    { "title": "Descriptive Diagram Title", "code": "sequenceDiagram\n    participant A as Component\n    participant B as Service\n    A->>B: Request\n    B-->>A: Response" },
    { "title": "Second Diagram Title", "code": "flowchart TD\n    A[Start] -->|step 1| B[Process]\n    B -->|validates| C{Decision}\n    C -->|yes| D[Success]\n    C -->|no| E[Retry]" }
  ]
}
"""

class MediaAgent:
    @classmethod
    async def generate_media(cls, db: Session, course_title: str, topic_title: str) -> dict:
        """
        Main entry point to get all media for a topic.
        Uses SWR cache for sub-100ms response if hit.
        """
        cache_key = f"{course_title}:{topic_title}"
        
        # AIRouter.generate_text already handles caching if we pass cache_key
        # but here we want to handle multiple API calls (YouTube, Flux)
        
        # Check if we have this in media_cache
        cached = await media_cache.get(cache_key)
        if cached:
            return cached

        # 1. Get LLM suggestions
        prompt = f"Topic: {topic_title}\nCourse: {course_title}\nPlease suggest media parameters."
        raw_json = await AIRouter.generate_text(
            db=db,
            prompt=prompt,
            system_instruction=SYSTEM_PROMPT,
            require_json=True
        )
        
        try:
            suggestions = json.loads(raw_json)
        except:
            suggestions = {
                "youtube_query": topic_title,
                "image_prompt": f"Educational image about {topic_title}",
                "diagrams": []
            }

        # 2. Get Real YouTube Video
        youtube_data = await cls._fetch_youtube_video(suggestions.get("youtube_query"))
        
        # 3. Trigger Image Generation (Async)
        image_url = await cls._generate_flux_image(suggestions.get("image_prompt"))

        result = {
            "youtube": youtube_data,
            "image": image_url,
            "diagrams": suggestions.get("diagrams", [])
        }

        # Save to cache
        await media_cache.set(cache_key, result)
        return result

    @classmethod
    async def _fetch_youtube_video(cls, query: Optional[str]) -> Optional[dict]:
        """Fetches the best matching video using YouTube Data API v3, with caching."""
        # Safety: Ensure query is a valid string
        query = (query or "Educational Video").strip()
        
        # Check cache first
        cache_key = f"yt:{query.lower()}"
        cached_res = await media_cache.get(cache_key)
        if cached_res and cached_res.get("video_id"):
            return cached_res
            
        if not settings.YOUTUBE_API_KEY:
            # If no API key, we return a fallback that the frontend can use to link to search
            return {
                "title": f"Search: {query}",
                "video_id": None,
                "embed_url": None,
                "watch_url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
                "thumbnail": None,
                "focus_area": "Full conceptual search results.",
                "search_query": query
            }

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 5, # Fetch more to allow for filtering
            "videoEmbeddable": "true", # CRITICAL: Only fetch embeddable videos
            "relevanceLanguage": "en",
            "key": settings.YOUTUBE_API_KEY
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    items = response.json().get("items", [])
                    if items:
                        # Find the first valid video item
                        for item in items:
                            video_id = item["id"].get("videoId")
                            if not video_id or video_id == "undefined":
                                continue
                                
                            result = {
                                "video_id": video_id,
                                "title": item["snippet"]["title"],
                                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                                "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1&origin={settings.FRONTEND_URL or 'http://localhost:5173'}",
                                "watch_url": f"https://www.youtube.com/watch?v={video_id}",
                                "focus_area": "Visual masterclass deep-dive.",
                                "search_query": query
                            }
                            await media_cache.set(cache_key, result)
                            return result
        except Exception as e:
            logger.error(f"YouTube API error: {e}")
        
        fallback = {
            "title": f"Search: {query}",
            "video_id": None, 
            "embed_url": None,
            "watch_url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
            "thumbnail": None,
            "focus_area": "Search for alternative curated videos.",
            "search_query": query
        }
        await media_cache.set(cache_key, fallback)
        return fallback

    @classmethod
    async def _generate_flux_image(cls, prompt: str) -> Optional[str]:
        """Generates or reuses a FLUX.1 image via Replicate."""
        if not settings.REPLICATE_API_TOKEN:
            return None

        # Check for reuse (Cache check)
        norm_prompt = prompt.lower().strip()
        cached_img = await media_cache.get(f"img:{norm_prompt}")
        if cached_img:
            return cached_img

        try:
            # Replicate API call (Simplified)
            # Flux model: black-forest-labs/flux-schnell
            url = "https://api.replicate.com/v1/predictions"
            headers = {"Authorization": f"Token {settings.REPLICATE_API_TOKEN}"}
            payload = {
                "version": "f13610b42e650222e499ca9aae995303f90ca56f7e3d0af3481846b7a950585f", # flux-schnell
                "input": {"prompt": prompt}
            }

            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 201:
                    prediction = response.json()
                    poll_url = prediction["urls"]["get"]
                    
                    # Poll for completion (max 30s)
                    for _ in range(15):
                        p_res = await client.get(poll_url, headers=headers)
                        p_data = p_res.json()
                        if p_data["status"] == "succeeded":
                            img_url = p_data["output"][0]
                            await media_cache.set(f"img:{norm_prompt}", img_url)
                            return img_url
                        elif p_data["status"] == "failed":
                            return None
                        await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"FLUX Image Gen error: {e}")
            
        return None

def generate_media_for_topic(course_title: str, topic_title: str, topic_content: str = ""):
    """Legacy wrapper for synchronous calls if needed, but endpoint should be async."""
    # This is a bit of a hack to keep existing code working while we migrate
    return {
        "youtube": {"search_query": topic_title},
        "diagrams": []
    }
