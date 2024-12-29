import socketio
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class SocketManager:
    def __init__(self):
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',
            logger=True,
            engineio_logger=True
        )
        
        self.app = socketio.ASGIApp(
            socketio_server=self.sio,
            socketio_path='socket.io'
        )
        
        self.active_connections: Dict[str, str] = {}
        
    async def connect(self, sid: str, user_id: str):
        """Store new socket.io connection"""
        self.active_connections[user_id] = sid
        logger.info(f"New connection: {user_id}")

    def disconnect(self, user_id: str):
        """Remove socket.io connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"Connection removed: {user_id}")

    async def send_message(self, user_id: str, message: Dict[str, Any]):
        """Send message to specific client"""
        if user_id in self.active_connections:
            try:
                sid = self.active_connections[user_id]
                await self.sio.emit('message', message, room=sid)
                logger.info(f"Message sent to {user_id}")
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {str(e)}")
        else:
            logger.warning(f"Inactive connection: {user_id}")

socket_manager = SocketManager()