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
        
        self.active_connections: Dict[str, str] = {}  # conversation_id -> sid mapping
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
        # Find and remove the conversation_id associated with this sid
        conversation_id = None
        for conv_id, session_id in self.active_connections.items():
            if session_id == sid:
                conversation_id = conv_id
                break
        
        if conversation_id:
            del self.active_connections[conversation_id]
            # Don't remove from welcomed_conversations to remember it was welcomed
            logger.info(f"Socket.IO connection removed for conversation: {conversation_id}")

    async def handle_chat_message(self, sid, data):
        """Handle incoming socket.io messages"""
        try:
            from app.services.ayla.ayla_agent import AylaAgentService
            from app.dependencies.depends import get_ayla_agent
            from app.schemas.ayla_agent_schemas import AylaAgentRequest

            
            logger.info(f"Received Socket.IO message from {sid}: {data}")
            
            # Create AylaAgentRequest from received data
            request = AylaAgentRequest(**data)
            
            # Store the socket connection
            await self.connect(sid, request.conversation_id)
            
            # Get AylaAgentService instance
            ayla_agent = get_ayla_agent(db=self.db)
            
            # Handle the request
            await ayla_agent.handle_websocket_request(sid, request)
            
        except Exception as e:
            logger.error(f"Socket.IO error in handle_chat_message: {str(e)}")
            await self.sio.emit('error', {'message': str(e)}, room=sid)

    async def connect(self, sid: str, conversation_id: str):
        """Store new socket.io connection"""
        self.active_connections[conversation_id] = sid
        logger.info(f"New Socket.IO connection added: {conversation_id}")

    def disconnect(self, conversation_id: str):
        """Remove socket.io connection"""
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
            logger.info(f"Socket.IO connection removed: {conversation_id}")

    async def send_message(self, conversation_id: str, message: dict):
        """Send message to specific client"""
        if conversation_id in self.active_connections:
            try:
                sid = self.active_connections[conversation_id]
                await self.sio.emit('message', message, room=sid)
                logger.info(f"Message sent to {conversation_id}")
            except Exception as e:
                logger.error(f"Error sending message to {conversation_id}: {str(e)}")
        else:
            logger.warning(f"Attempted to send message to inactive connection: {conversation_id}")
