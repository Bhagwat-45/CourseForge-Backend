import httpx
import logging
from typing import Optional
from app.core.config import settings

from app.core.metrics import metrics
logger = logging.getLogger(__name__)

class TTSService:
    """
    Multi-level TTS Service for Nova.
    Primary: Hugging Face MMS-TTS
    Fallback: Signaling the frontend to use browser speech extraction
    """
    HF_TTS_MODEL = "facebook/mms-tts-eng"

    @classmethod
    async def generate_audio(cls, text: str) -> Optional[bytes]:
        """
        Generates audio bytes for the given text using Hugging Face.
        Returns None if API fails, allowing frontend to fallback.
        """
        if not settings.HF_API_KEY:
            logger.warning("HF_API_KEY not configured. Skipping backend TTS.")
            return None

        from huggingface_hub import AsyncInferenceClient
        client = AsyncInferenceClient(token=settings.HF_API_KEY)

        try:
            metrics.record_request()
            response = await client.text_to_speech(text, model=cls.HF_TTS_MODEL)
            metrics.record_success(0) # Latency tracking for TTS can be added if desired
            return response
        except Exception as e:
            logger.error(f"[AI_ERROR] provider=huggingface_tts reason=\"{str(e)}\" retry=0/1")
            metrics.record_failure(fallback=True)
            return None

ttsservice = TTSService()
