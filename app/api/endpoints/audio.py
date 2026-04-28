from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.core.database import get_db
from app.api.endpoints.auth import get_current_user
from app.models.models import User
from app.core.audio import ttsservice

router = APIRouter()

@router.get("/speech")
async def get_speech(
    text: str = Query(..., description="The text to convert to speech"),
    current_user: User = Depends(get_current_user),
):
    """
    Converts text to speech using Hugging Face.
    Returns audio/mpeg stream or 404 if TTS fails (signaling browser fallback).
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    audio_bytes = await ttsservice.generate_audio(text)
    
    if not audio_bytes:
        # We return a specific header or 204 No Content to tell the frontend
        # to use the browser API instead.
        return Response(status_code=204)

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg"
    )
