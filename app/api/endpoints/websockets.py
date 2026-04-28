from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.websockets import manager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/{topic_id}")
async def topic_status_websocket(websocket: WebSocket, topic_id: int):
    """
    WebSocket endpoint for real-time topic generation status.
    """
    await manager.connect(websocket, topic_id)
    try:
        while True:
            # Keep connection alive and wait for client messages (if any)
            # Or just wait for disconnect
            data = await websocket.receive_text()
            # We don't expect data from client yet, but we keep it open
    except WebSocketDisconnect:
        manager.disconnect(websocket, topic_id)
    except Exception as e:
        logger.error(f"WebSocket error for topic {topic_id}: {e}")
        manager.disconnect(websocket, topic_id)
