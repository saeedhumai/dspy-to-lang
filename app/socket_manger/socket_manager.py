import socketio
from typing import Dict
from configs.logger import logger
from motor.motor_asyncio import AsyncIOMotorClient


class SocketManager:
    def __init__(self, db: AsyncIOMotorClient):
        self.db = db
        # Create Socket.IO server with CORS and other settings
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',
            logger=True,
            engineio_logger=True
        )
        
        # Create ASGI app
        self.app = socketio.ASGIApp(
            socketio_server=self.sio,
            other_asgi_app=None,
            socketio_path='socket.io'  # Changed from /ws/socket.io
        )
        
        self.active_connections: Dict[str, str] = {}  # user_id -> sid mapping
        self.welcomed_conversations: set = set()  # Track welcomed conversations
        
        # Register event handlers
        self.sio.on('connect', self.handle_connect)
        self.sio.on('disconnect', self.handle_disconnect)
        self.sio.on('chat_message', self.handle_chat_message)


    async def handle_connect(self, sid, environ):
        """Handle new socket.io connections"""
        logger.info(f"New Socket.IO connection: {sid}")

    async def handle_disconnect(self, sid):
        """Handle socket.io disconnections"""
        # Find and remove the user_id associated with this sid
        user_id = None
        for conv_id, session_id in self.active_connections.items():
            if session_id == sid:
                user_id = conv_id
                break
        
        if user_id:
            del self.active_connections[user_id]
            # Don't remove from welcomed_conversations to remember it was welcomed
            logger.info(f"Socket.IO connection removed for conversation: {user_id}")

    # Modified socket_manager.py for Ayla
    async def handle_chat_message(self, sid, data):
        from app.schemas.ayla_agent_schemas import AylaAgentRequest
        from app.dependencies.depends import get_ayla_agent
        import uuid
        try:
            request = AylaAgentRequest(**data)
            ayla_agent = get_ayla_agent(db=self.db)
            
            # Store connection before processing
            await self.connect(sid, request.user_id)
            
            # Add correlation ID for tracking
            correlation_id = str(uuid.uuid4())
            data['correlation_id'] = correlation_id
            
            # Handle the request
            await ayla_agent.handle_websocket_request(sid, request)
            
        except Exception as e:
            logger.error(f"Socket.IO error: {str(e)}")
            await self.sio.emit('error', {
                'correlation_id': data.get('correlation_id'),
                'message': str(e)
            }, room=sid)

    async def connect(self, sid: str, user_id: str):
        """Store new socket.io connection"""
        self.active_connections[user_id] = sid
        logger.info(f"New Socket.IO connection added: {user_id}")

    def disconnect(self, user_id: str):
        """Remove socket.io connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"Socket.IO connection removed: {user_id}")

    async def send_message(self, user_id: str, message: dict):
        """Send message to specific client"""
        if user_id in self.active_connections:
            try:
                sid = self.active_connections[user_id]
                await self.sio.emit('message', message, room=sid)
                logger.info(f"Message sent to {user_id}")
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {str(e)}")
        else:
            logger.warning(f"Attempted to send message to inactive connection: {user_id}")
