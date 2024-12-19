import socketio
import asyncio
from typing import Dict, Any, Optional
from configs.logger import logger
from configs.settings import Settings
from app.socket_manger.socket_manager import SocketManager

class OzilClient:
    def __init__(self, settings: Settings, socket_manager: SocketManager):
        self.ozil_url = settings.OZIL_SERVICE_URL
        self.socket_manager = socket_manager
        self.ozil_socket: Optional[socketio.AsyncClient] = None
        self.active_conversations: Dict[str, bool] = {}
        self._initialization_lock = asyncio.Lock()
        self._initialization_task = None

    async def initialize_socket(self):
        """Initialize and maintain persistent socket connection to Ozil"""
        async with self._initialization_lock:
            if self.ozil_socket is not None and self.ozil_socket.connected:
                return

            try:
                logger.info(f"Ozil socket not initialized: {self.ozil_socket}")
                self.ozil_socket = socketio.AsyncClient(
                    reconnection=True,
                    reconnection_attempts=0,
                    reconnection_delay=1,
                    reconnection_delay_max=5,
                    logger=logger
                )
                
                # Set up event handlers
                @self.ozil_socket.on('connect')
                async def on_connect():
                    logger.info("Successfully connected to Ozil service")
                
                @self.ozil_socket.on('disconnect')
                async def on_disconnect():
                    logger.warning("Disconnected from Ozil service")

                @self.ozil_socket.on('message_ack')
                async def on_message_ack(data):
                    logger.info(f"Message acknowledged by Ozil: {data}")

                @self.ozil_socket.on('connect_error')
                async def on_connect_error(data):
                    logger.error(f"Connection error to Ozil service: {data}")
                
                @self.ozil_socket.on('*')
                async def catch_all(event, data):
                    logger.debug(f"Received event {event}: {data}")
                
                await asyncio.wait_for(
                    self.ozil_socket.connect(self.ozil_url),
                    timeout=5.0
                )
                
            except Exception as e:
                logger.error(f"Error in Ozil socket initialization: {str(e)}")
                if self.ozil_socket:
                    await self.ozil_socket.disconnect()
                    self.ozil_socket = None
                raise

    async def maintain_connection(self):
        """Background task to maintain socket connection"""
        while True:
            try:
                if self.ozil_socket is None or not self.ozil_socket.connected:
                    await self.initialize_socket()
                
                await asyncio.sleep(5)
                
                if self.ozil_socket and self.ozil_socket.connected:
                    await self.ozil_socket.emit('ping')
                    
            except Exception as e:
                logger.error(f"Error in maintain_connection: {str(e)}")
                await asyncio.sleep(2)

    async def send_message(self, parsed_response: Dict[str, Any], user_id: str, language: str = 'en', provider: str = 'openai', model: str = 'gpt-4'):
        """Send message to Ozil service"""
        try:
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    if self.ozil_socket is None or not self.ozil_socket.connected:
                        await self.initialize_socket()
                    
                    ozil_message = {
                        "user_id": user_id,
                        "message": parsed_response["ayla_response"],
                        "product": parsed_response["product"],
                        "quantity": parsed_response["quantity"],
                        "supplier_type": parsed_response["supplier_type"],
                        "language": language,
                        "provider": provider,
                        "model": model
                    }

                    await self.ozil_socket.emit('message_to_ozil', ozil_message)
                    logger.info("Message sent to Ozil successfully")
                    return
                    
                except Exception as e:
                    logger.error(f"Attempt {retry_count + 1} failed: {str(e)}")
                    retry_count += 1
                    await asyncio.sleep(1)
                    
            raise Exception("Failed to send message after multiple attempts")

        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            await self.socket_manager.send_message(
                user_id,
                {
                    "done": True,
                    "type": "error",
                    "content": "An error occurred while processing your request. Please try again. From Ayla [ERROR]",
                    "sender": "ai"
                }
            ) 