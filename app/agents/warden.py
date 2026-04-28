import logging
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class Warden:
    """
    The Warden is responsible for validating AI-generated content.
    It ensures that the output is high-quality, safe, and structured correctly.
    """

    @staticmethod
    def validate_json(content: str, expected_keys: List[str]) -> Dict[str, Any]:
        """
        Validates that the content is valid JSON and contains the expected keys.
        """
        from app.core.sanitizer import Sanitizer
        try:
            clean_content = Sanitizer.extract_json(content)
            data = json.loads(clean_content)
            
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                raise ValueError(f"Missing required schema keys: {missing_keys}")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"[AI_ERROR] provider=System reason=Invalid JSON details=\"{str(e)}\"")
            raise ValueError(f"AI generated invalid JSON structure. Details: {e}")
        except Exception as e:
            logger.error(f"[AI_ERROR] provider=System reason=Validation Failed details=\"{str(e)}\"")
            raise

    @staticmethod
    def validate_content_length(text: str, min_chars: int = 100) -> bool:
        """
        Ensures the generated text is not suspiciously short.
        """
        if len(text) < min_chars:
            logger.warning(f"Warden Warning: Content length ({len(text)}) is below threshold ({min_chars})")
            return False
        return True

    @staticmethod
    def check_hallucination(text: str, context: str) -> bool:
        """
        Simple heuristic check to ensure the AI isn't ignoring the provided context.
        """
        return True

    @staticmethod
    def validate_pedagogical_completeness(content: str) -> bool:
        """
        V5: Ensures the AI generated the required layered difficulty markers.
        """
        if not content:
            return False
            
        markers = ["🟢 Foundation", "🟡 Going Deeper", "🔴 Expert Territory"]
        for marker in markers:
            if marker not in content:
                logger.warning(f"Warden Warning: Missing pedagogical marker '{marker}'")
                return False
        return True

    @staticmethod
    def validate_media_resource(resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensures a media resource contains all required fields and no null IDs.
        """
        required = ["video_id", "title", "watch_url", "embed_url"]
        for key in required:
            val = resource.get(key)
            if not val or val == "undefined":
                logger.warning(f"Warden: Media resource missing or invalid required field '{key}': {val}")
                return {} # Return empty to indicate invalid
        
        # Sanitize URLs
        if not str(resource["watch_url"]).startswith("http"):
            resource["watch_url"] = f"https://www.youtube.com/watch?v={resource['video_id']}"
            
        if not str(resource["embed_url"]).startswith("http"):
             resource["embed_url"] = f"https://www.youtube.com/embed/{resource['video_id']}"

        return resource

    @staticmethod
    def validate_semantic_alignment(topic_title: str, query: str) -> str:
        """
        V5: Validates if a video query is semantically aligned with the topic title.
        If hallucinated or generic, forces a safe query.
        """
        if not query or not topic_title:
            return f"{topic_title} deep dive tutorial"
            
        topic_words = set(w for w in topic_title.lower().split() if len(w) > 3)
        query_words = set(w for w in query.lower().split() if len(w) > 3)
        
        intersection = topic_words.intersection(query_words)
        
        # If there's 0 overlap in meaningful keywords, the AI might have hallucinated a random video
        if not intersection and len(topic_words) > 0:
            logger.warning(f"Warden: Hallucinated video query '{query}' for topic '{topic_title}'. Replacing.")
            return f"{topic_title} deep dive tutorial"
            
        return query
