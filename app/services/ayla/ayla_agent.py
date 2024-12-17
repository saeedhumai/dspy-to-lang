import dspy
from typing import Dict, Any, Optional
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, UTC
from app.schemas.ayla_agent_schemas import AylaAgentRequest
from app.core.ayla_document_processor import AylaDocumentProcessor
from configs.logger import logger
from configs.settings import Settings
from app.core.dima_http_client import DimaHttpClient
from app.core.ayla_voice_processor import AudioProcessor
from app.core.diana_http_client import DianaHttpClient
from app.socket_manger.socket_manager import SocketManager
import socketio
import asyncio
from app.services.ayla.dspy_config import DSPyManager

class ChatResponse(dspy.Signature):
    """Process user requests for product quotes step by step."""
    message: str = dspy.InputField(desc="User's input message")
    messages: list = dspy.InputField(desc="Conversation history")
    ayla_response: str = dspy.OutputField(desc="Ayla's response to the user")
    to_ozil: bool = dspy.OutputField(desc="Whether to forward to Ozil service")
    confirmation_status: str = dspy.OutputField(desc="Current confirmation status: 'product', 'quantity', 'supplier_type', or 'complete'")
    confirmed_product: Optional[str] = dspy.OutputField(desc="Confirmed product name")
    confirmed_quantity: Optional[int] = dspy.OutputField(desc="Confirmed quantity")
    confirmed_supplier_type: Optional[str] = dspy.OutputField(desc="Confirmed supplier type (private/public/both)")

class AylaAgentService:
    def __init__(self, 
                 db: AsyncIOMotorClient, 
                 document_processor: AylaDocumentProcessor,
                 audio_processor: AudioProcessor,
                 socket_manager: SocketManager,
                 dima_client: DimaHttpClient,
                 diana_client: DianaHttpClient,
                 settings: Settings):
        self.db = db
        self.document_processor = document_processor
        self.dima_client = dima_client
        self.diana_client = diana_client
        self.audio_processor = audio_processor
        self.settings = settings
        self.socket_manager = socket_manager
        self.chat_processor = dspy.ChainOfThought(ChatResponse)
        self.dspy_manager = DSPyManager()

        # Initialize Ozil socket client at service level
        self.ozil_socket: Optional[socketio.AsyncClient] = None
        self.ozil_url = settings.OZIL_SERVICE_URL
        self.active_conversations: Dict[str, bool] = {}
        
        # Initialize the socket connection
        # asyncio.create_task(self.initialize_ozil_socket())


    async def get_active_conversation(self, user_id: str) -> Optional[Dict]:
        """Get the most recent incomplete conversation for a user"""
        conversation = await self.db.conversations.find_one({
            "user_id": user_id,
            "status": "active",
            "confirmation_context.status": {"$ne": "complete"}
        }, sort=[("created_at", -1)])
        return conversation

    async def create_new_conversation(self, user_id: str) -> str:
        """Create a new conversation and return its ID"""
        result = await self.db.conversations.insert_one({
            "user_id": user_id,
            "status": "active",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "messages": [],
            "confirmation_context": {
                "status": "product",
                "product": None,
                "quantity": None,
                "supplier_type": None
            }
        })
        return str(result.inserted_id)

    async def save_message(self, conversation_id: str, content: str, sender: str, type: str = None) -> None:
        """Save a message to the conversation history"""
        message_data = {
            "content": content,
            "sender": sender,
            "time": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
            "type": type
        }
        
        await self.db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$push": {"messages": message_data},
                "$set": {"updated_at": datetime.now(UTC)}
            }
        )

    async def handle_websocket_request(self, sid: str, request: AylaAgentRequest):
        """Handle chat request via Socket.IO using DSPy"""
        logger.info(f"Processing request for user_id: {request.user_id}")
        
        # Get active conversation or create new one
        conversation = await self.get_active_conversation(request.user_id)
        
        if not conversation:
            # Create new conversation if there's no active incomplete one
            conversation_id = await self.create_new_conversation(request.user_id)
            conversation = await self.db.conversations.find_one({"_id": ObjectId(conversation_id)})
        else:
            conversation_id = str(conversation["_id"])

        confirmation_context = conversation.get("confirmation_context", {})
        
        # Get conversation history and format it for DSPy
        messages = [
            {
                "role": "system",
                "content": """You are Ayla, a professional procurement assistant. Your task is to confirm product quote requests step by step, one detail at a time.

IMPORTANT RULES:
1. You must confirm ONE detail at a time in this exact order: product → quantity → supplier type
2. Do not move to the next detail until the current one is explicitly confirmed by the user
3. For each detail:
   - Product: Ask for specific product name/details if unclear
   - Quantity: Must be a positive number
   - Supplier Type: Must be exactly 'private', 'public', or 'both'
4. Set confirmation_status based on which detail you're currently confirming
5. Only set to_ozil=True when all details are confirmed

Current Status: {status}
Confirmed Details:
- Product: {product}
- Quantity: {quantity}
- Supplier Type: {supplier_type}""".format(
                    status=confirmation_context.get("status", "product"),
                    product=confirmation_context.get("product", "Not confirmed"),
                    quantity=confirmation_context.get("quantity", "Not confirmed"),
                    supplier_type=confirmation_context.get("supplier_type", "Not confirmed")
                )
            }
        ]
        
        if "messages" in conversation:
            for msg in conversation["messages"]:
                role = "assistant" if msg["sender"] == "ai" else "user"
                messages.append({
                    "role": role,
                    "content": msg["content"]
                })
        
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        try:
            self.dspy_manager.configure_default_lm(
                provider=request.provider, 
                model=request.model, 
                temperature=0.2
            )

            predict = dspy.Predict(ChatResponse)
            response = predict(
                message=request.message,
                messages=messages
            )
            logger.info(f"Response: {response}")
            
            # Save AI response
            await self.save_message(
                conversation_id=conversation_id,
                content=response.ayla_response,
                sender="ai",
                type="text"
            )
            
            if response.to_ozil and response.confirmation_status == "complete":
                # Mark current conversation as complete
                await self.db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {
                        "$set": {
                            "status": "completed",
                            "completed_at": datetime.now(UTC),
                            "confirmation_context": {
                                "status": "complete",
                                "product": response.confirmed_product,
                                "quantity": response.confirmed_quantity,
                                "supplier_type": response.confirmed_supplier_type
                            }
                        }
                    }
                )

                logger.info("*********************************************************")
                logger.info(f"Calling Ozil Process Response Method")
                logger.info("*********************************************************")
                
                await self.process_response({
                    "ayla_response": response.ayla_response,
                    "product": response.confirmed_product,
                    "quantity": response.confirmed_quantity,
                    "supplier_type": response.confirmed_supplier_type,
                    "to_ozil": True
                }, conversation_id)
            else:
                await self.db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {
                        "$set": {
                            "confirmation_context": {
                                "status": response.confirmation_status,
                                "product": response.confirmed_product,
                                "quantity": response.confirmed_quantity,
                                "supplier_type": response.confirmed_supplier_type
                            }
                        }
                    }
                )
                
                await self.socket_manager.send_message(
                    request.user_id,
                    {
                        "done": True,
                        "type": "text",
                        "content": response.ayla_response,
                        "sender": "ai"
                    }
                )
            
        except Exception as e:
            logger.error(f"Error in handle_websocket_request: {str(e)}")
            await self.save_message(
                conversation_id=request.user_id,
                content=f"An error occurred while processing your request: {str(e)}",
                sender="ai",
                type="text"
            )
            await self.socket_manager.send_message(
                request.user_id,
                {"done": True, "type": "text", "content": "An error occurred while processing your request.", "sender": "ai"}
            )

    async def initialize_ozil_socket(self):
        """Initialize and maintain persistent socket connection to Ozil"""
        while True:
            try:
                if self.ozil_socket is None or not self.ozil_socket.connected:
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
                    
                    @self.ozil_socket.on('connect_error')
                    async def on_connect_error(data):
                        logger.error(f"Connection error to Ozil service: {data}")
                    
                    # Your existing event handlers...
                    
                    # Connect to Ozil with timeout
                    await asyncio.wait_for(
                        self.ozil_socket.connect(self.ozil_url),
                        timeout=10.0
                    )
                
                # If connected, maintain connection
                await asyncio.sleep(30)
                
            except asyncio.TimeoutError:
                logger.error("Timeout while connecting to Ozil service")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error in Ozil socket connection: {str(e)}")
                await asyncio.sleep(5)
                
            if self.ozil_socket:
                try:
                    await self.ozil_socket.disconnect()
                except:
                    pass
                self.ozil_socket = None


    async def process_response(self, parsed_response: Dict[str, Any], conversation_id: str):
        """Process response from LLM and dispatch to relevant agent."""
        try:
            # Add conversation to active conversations
            self.active_conversations[conversation_id] = True

            # Add necessary data for Ozil
            ozil_message = {
                "user_id": conversation_id,
                "language": getattr(self, '_language', 'en'),
                "provider": getattr(self, '_provider', 'openai'),
                "model": getattr(self, '_model', 'gpt-4o')
            }

            # Send initial message to frontend
            await self.socket_manager.send_message(
                conversation_id,
                {
                    "done": False,
                    "type": "text",
                    "content": parsed_response["ayla_response"],
                    "sender": "ai"
                }
            )

            # If socket is connected, send message to Ozil
            if self.ozil_socket and self.ozil_socket.connected:
                await self.ozil_socket.emit('message_to_ozil', ozil_message)
            else:
                raise Exception("No connection to Ozil service")

        except Exception as e:
            logger.error(f"Error in process_response: {str(e)}")
            await self.socket_manager.send_message(
                conversation_id,
                {
                    "done": True,
                    "type": "error",
                    "content": "An error occurred while processing your request.",
                    "sender": "ai"
                }
            )