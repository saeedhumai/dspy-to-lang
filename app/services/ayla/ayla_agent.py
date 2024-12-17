import dspy
from langchain_mongodb import MongoDBChatMessageHistory
from typing import Dict, Any, Optional
from fastapi import HTTPException
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

# Define DSPy signatures for our chat system
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
        
        # Configure DSPy with the appropriate LM
        # self._configure_dspy()

        self.chat_processor = dspy.ChainOfThought(ChatResponse)
        # self.chat_processor.preset_prompt = confirmation_prompt
        self.dspy_manager = DSPyManager()


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
                "$setOnInsert": {"created_at": datetime.now(UTC)},
                "$set": {"updated_at": datetime.now(UTC)}
            },
            upsert=True
        )

    async def handle_websocket_request(self, sid: str, request: AylaAgentRequest):
        """Handle chat request via Socket.IO using DSPy"""
        logger.info(f"Processing request for user_id: {request.conversation_id}")
        
        # Get existing conversation state and history from database
        conversation = await self.db.conversations.find_one({"_id": ObjectId(request.conversation_id)})
        confirmation_context = conversation.get("confirmation_context", {}) if conversation else {}
        
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

    ## **Example interaction flow:**
    User: "I need quotes for 200 units of Product X from private suppliers"
    Ayla: "You mentioned Product X. Could you please confirm if this is exactly what you're looking for?"

    User: "Yes, that's correct"
    Ayla: "You mentioned 200 units. Is this the exact quantity you need?"

    User: "Yes, 200 units"
    Ayla: "Lastly, you specified private suppliers. Should I exclusively look for quotes from private suppliers?"

    User: "Yes, private suppliers only"
    Ayla: "Perfect! I'll now search for quotes for 200 units of Product X from private suppliers only."


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
        
        if conversation and "messages" in conversation:
            for msg in conversation["messages"]:
                role = "assistant" if msg["sender"] == "ai" else "user"
                messages.append({
                    "role": role,
                    "content": msg["content"]
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        logger.info("--------------------------------")
        logger.info(f"Messages: {messages}")
        logger.info("--------------------------------")

        try:
            logger.info("Configuring LM")
            self.dspy_manager.configure_default_lm(
                provider=request.provider, 
                model=request.model, 
                temperature=0.2
            )

            # Process with DSPy
            predict = dspy.Predict(ChatResponse)
            response = predict(
                message=request.message,
                messages=messages
            )
            logger.info(f"Response: {response}")
            
            # Save AI response
            await self.save_message(
                conversation_id=request.conversation_id,
                content=response.ayla_response,
                sender="ai",
                type="text"
            )
            
            # Update confirmation context in database
            await self.db.conversations.update_one(
                {"_id": ObjectId(request.conversation_id)},
                {
                    "$set": {
                        "confirmation_context": {
                            "status": response.confirmation_status,
                            "product": response.confirmed_product,
                            "quantity": response.confirmed_quantity,
                            "supplier_type": response.confirmed_supplier_type
                        }
                    }
                },
                upsert=True
            )
            
            # Only forward to Ozil if all confirmations are complete
            if response.to_ozil and response.confirmation_status == "complete":
                await self.process_response({
                    "ayla_response": response.ayla_response,
                    "to_ozil": True
                }, request.conversation_id)
            else:
                # Send direct response
                await self.socket_manager.send_message(
                    request.conversation_id,
                    {
                        "done": True,
                        "type": "text",
                        "content": response.ayla_response,
                        "sender": "ai"
                    }
                )
        except Exception as e:
            logger.error(f"Error in handle_websocket_request: {str(e)}")
            # Save error message
            await self.save_message(
                conversation_id=request.conversation_id,
                content=f"An error occurred while processing your request: {str(e)}",
                sender="ai",
                type="text"
            )
            await self.socket_manager.send_message(
                request.conversation_id,
                {"done": True, "type": "text", "content": "An error occurred while processing your request.", "sender": "ai"}
            )


    async def initialize_ozil_socket(self):
        """Initialize and maintain persistent socket connection to Ozil"""
        while True:
            try:
                if self.ozil_socket is None or not self.ozil_socket.connected:
                    self.ozil_socket = socketio.AsyncClient(reconnection=True, reconnection_attempts=0)
                    
                    # Set up event handlers
                    @self.ozil_socket.on('search_status')
                    async def on_search_status(data):
                        conversation_id = data.get('conversation_id')
                        if conversation_id in self.active_conversations:
                            await self.socket_manager.send_message(
                                conversation_id,
                                {
                                    "done": False,
                                    "type": "search_status",
                                    "content": data["content"],
                                    "sender": "ai"
                                }
                            )

                    @self.ozil_socket.on('search_results')
                    async def on_search_results(data):
                        conversation_id = data.get('conversation_id')
                        if conversation_id in self.active_conversations:
                            # Save the message with products if available
                            await self.save_message(
                                conversation_id=conversation_id,
                                content=data["content"],
                                sender="ai",
                                type="text",
                                products=data.get("products", [])
                            )
                            
                            # Forward to frontend
                            await self.socket_manager.send_message(
                                conversation_id,
                                {
                                    "done": data["done"],
                                    "type": "search_results",
                                    "content": data["content"],
                                    "products": data.get("products", []),
                                    "sender": "ai"
                                }
                            )

                    @self.ozil_socket.on('search_error')
                    async def on_search_error(data):
                        conversation_id = data.get('conversation_id')
                        if conversation_id in self.active_conversations:
                            await self.save_message(
                                conversation_id=conversation_id,
                                content=data["content"],
                                sender="ai",
                                type="text"
                            )
                            
                            await self.socket_manager.send_message(
                                conversation_id,
                                {
                                    "done": True,
                                    "type": "search_error",
                                    "content": data["content"],
                                    "sender": "ai"
                                }
                            )

                    @self.ozil_socket.on('disconnect')
                    async def on_disconnect():
                        logger.warning("Disconnected from Ozil. Attempting to reconnect...")
                        await asyncio.sleep(5)  # Wait before reconnect attempt

                    # Connect to Ozil
                    await self.ozil_socket.connect(self.ozil_url)
                    logger.info("Successfully connected to Ozil service")
                
                # If connected, just wait and maintain connection
                await asyncio.sleep(30)  # Check connection every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in Ozil socket connection: {str(e)}")
                await asyncio.sleep(5)  # Wait before retry



    async def process_response(self, parsed_response: Dict[str, Any], conversation_id: str):
        """Process response from LLM and dispatch to relevant agent."""
        try:
            # # Add conversation to active conversations
            # self.active_conversations[conversation_id] = True

            # Add necessary data for Ozil
            ozil_message = {
                "name": parsed_response.get("user_name", ""),
                "conversation_id": conversation_id,
                "language": getattr(self, '_language', 'en'),
                "provider": getattr(self, '_provider', 'openai'),
                "model": getattr(self, '_model', 'gpt-4o')
            }

            # Save initial message from Ayla
            await self.save_message(
                conversation_id=conversation_id,
                content=parsed_response["ayla_response"],
                sender="ai",
                type="text"
            )

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