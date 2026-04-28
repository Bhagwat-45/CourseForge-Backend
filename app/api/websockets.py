import json
import asyncio
from typing import Dict, List, Set
from fastapi import WebSocket
from app.core.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections and bridges them with Redis Pub/Sub.
    Enables real-time updates across multiple backend instances.
    """
    def __init__(self):
        # topic_id -> set of WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.pubsub_task = None

    async def connect(self, websocket: WebSocket, topic_id: int):
        await websocket.accept()
        if topic_id not in self.active_connections:
            self.active_connections[topic_id] = set()
        self.active_connections[topic_id].add(websocket)
        logger.info(f"Client connected to topic {topic_id}. Total: {len(self.active_connections[topic_id])}")

    def disconnect(self, websocket: WebSocket, topic_id: int):
        if topic_id in self.active_connections:
            self.active_connections[topic_id].discard(websocket)
            if not self.active_connections[topic_id]:
                del self.active_connections[topic_id]
        logger.info(f"Client disconnected from topic {topic_id}")

    async def broadcast_to_topic(self, topic_id: int, message: dict):
        """Sends message to all clients subscribed to a specific topic on THIS instance."""
        if topic_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[topic_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.add(connection)
            
            for conn in disconnected:
                self.disconnect(conn, topic_id)

    async def notify_topic_update(self, topic_id: int, status: str, message: str = ""):
        """
        Public method to notify clients of a topic update.
        Bridges local broadcast and Redis Pub/Sub.
        """
        data = {
            "topic_id": topic_id,
            "status": status,
            "message": message
        }
        
        # 1. Local Broadcast (Immediate)
        await self.broadcast_to_topic(topic_id, data)
        
        # 2. Redis Publish (for other instances)
        if redis_client:
            try:
                redis_client.publish("topic_updates", json.dumps(data))
            except Exception as e:
                logger.warning(f"Failed to publish to Redis: {e}")

    async def start_pubsub_listener(self):
        """
        Listens to Redis Pub/Sub and broadcasts to local connections.
        This allows multi-instance scalability.
        """
        if not redis_client:
            logger.info("Redis client not available. Pub/Sub listener skipped (Single-instance mode).")
            return

        logger.info("Initializing Redis Pub/Sub listener...")
        
        while True:
            try:
                pubsub = redis_client.pubsub()
                pubsub.subscribe("topic_updates")
                logger.info("Subscribed to 'topic_updates' channel.")
                
                while True:
                    # Use get_message with timeout to avoid blocking forever
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        try:
                            data = json.loads(message['data'])
                            topic_id = data.get("topic_id")
                            if topic_id:
                                await self.broadcast_to_topic(topic_id, data)
                        except Exception as parse_err:
                            logger.error(f"Failed to parse Pub/Sub message: {parse_err}")
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Redis Pub/Sub connection failed: {e}. Retrying in 10s...")
                await asyncio.sleep(10) # Cooldown on failure

manager = ConnectionManager()
