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
from app.services.ayla.dspy_config import DSPyManager
from app.core.ozil_client import OzilClient

class ChatResponse(dspy.Signature):
    """Process user requests for product quotes step by step."""
    message: str = dspy.InputField(desc="User's input message")
    messages: list = dspy.InputField(desc="Conversation history")
    ayla_response: str = dspy.OutputField(desc="Ayla's response to the user")
    to_ozil: bool = dspy.OutputField(desc="Whether to forward to Ozil service")
    status: str = dspy.OutputField(desc="Current status: 'product', 'quantity', 'supplier_type', or 'complete'")
    product_name: Optional[str] = dspy.OutputField(desc="Processed product name")
    product_category: Optional[str] = dspy.OutputField(desc="Processed product category")
    quantity: Optional[int] = dspy.OutputField(desc="Processed quantity")
    supplier_type: Optional[str] = dspy.OutputField(desc="Processed supplier type (private/public/both)")
    brand: Optional[str] = dspy.OutputField(desc="Processed brand name")
    model: Optional[str] = dspy.OutputField(desc="Processed model name")
    description: Optional[str] = dspy.OutputField(desc="Processed description")
    delivery_location: Optional[str] = dspy.OutputField(desc="Processed delivery location")
    preferred_delivery_timeline: Optional[str] = dspy.OutputField(desc="Processed preferred delivery timeline")
    supplier_list_name: Optional[str] = dspy.OutputField(desc="Processed supplier list name")

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
        self.ozil_client = OzilClient(settings, socket_manager)

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
                "product_category": None,
                "quantity": None,
                "supplier_type": None,
                "brand": None,
                "model": None,
                "description": None,
                "delivery_location": None,
                "preferred_delivery_timeline": None,
                "supplier_list_name": None
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

        # Save user message first
        await self.save_message(
            conversation_id=conversation_id,
            content=request.message,
            sender="user",
            type="text"
        )

        confirmation_context = conversation.get("confirmation_context", {})
        
        # Get conversation history and format it for DSPy
        messages = [
            {
                "role": "system",
                "content": """You are Ayla, a professional procurement assistant. Your task is to process product quote requests step by step, one detail at a time.

IMPORTANT RULES:
1. You must process one detail at a time in this exact order: product → quantity → supplier type
2. Do not move to the next detail until the current one is explicitly answered by the user
3. For each detail:
    **Required:**
   - Product: Ask for specific product name/details if unclear
   - Quantity: Must be a positive number
   - Supplier Type: Must be exactly 'private', 'public', or 'both'

    **Optional:** Make `to_ozil=True` if user don't want to provide provide optional details.
   - Brand: Ask for specific brand name if unclear
   - Model: Ask for specific model name if unclear
   - Description: Ask for specific description if unclear
   - Delivery Location: Ask for specific delivery location if unclear
   - Preferred Delivery Timeline: Ask for specific delivery timeline if unclear
   - Supplier List Name: Ask for specific supplier list name if unclear

4. Set status based on which detail you're currently processing
5. Only set to_ozil=True user don't want to provide optional details or all details are processed. Based on User Input.

Current Status: {status}
Processed Details:
- Product: {product}
- Product Category: {product_category}
- Quantity: {quantity}
- Supplier Type: {supplier_type}
- Brand: {brand}
- Model: {model}
- Description: {description}
- Delivery Location: {delivery_location}
- Preferred Delivery Timeline: {preferred_delivery_timeline}
- Supplier List Name: {supplier_list_name}
""".format(
                    status=confirmation_context.get("status", "product"),
                    product=confirmation_context.get("product", "Not processed"),
                    product_category=confirmation_context.get("product_category", "Not processed"),
                    quantity=confirmation_context.get("quantity", "Not processed"),
                    supplier_type=confirmation_context.get("supplier_type", "Not processed"),
                    brand=confirmation_context.get("brand", "Not processed"),
                    model=confirmation_context.get("model", "Not processed"),
                    description=confirmation_context.get("description", "Not processed"),
                    delivery_location=confirmation_context.get("delivery_location", "Not processed"),
                    preferred_delivery_timeline=confirmation_context.get("preferred_delivery_timeline", "Not processed"),
                    supplier_list_name=confirmation_context.get("supplier_list_name", "Not processed")
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
            
            if response.to_ozil and response.status == "complete":
                # Mark current conversation as complete
                await self.db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {
                        "$set": {
                            "status": "completed",
                            "completed_at": datetime.now(UTC),
                            "confirmation_context": {
                                "status": "complete",
                                "product": response.product_name,
                                "product_category": response.product_category,
                                "quantity": response.quantity,
                                "supplier_type": response.supplier_type,
                                "brand": response.brand,
                                "model": response.model,
                                "description": response.description,
                                "delivery_location": response.delivery_location,
                                "preferred_delivery_timeline": response.preferred_delivery_timeline,
                                "supplier_list_name": response.supplier_list_name
                            }
                        }
                    }
                )

                logger.info("*********************************************************")
                logger.info(f"Calling Ozil Process Response Method")
                logger.info("*********************************************************")

                # Send initial message to frontend
                await self.socket_manager.send_message(
                    request.user_id,
                    {
                        "done": False,
                        "type": "text",
                        "content": response.ayla_response,
                        "sender": "ai"
                    }
                )

                response.user_id = request.user_id
                response.language = request.language if request.language else "en"
                response.provider = request.provider if request.provider else "openai"
                response.model = request.model if request.model else "gpt-4o"

                response = response.toDict()
                
                await self.process_response(response)
            else:
                await self.db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {
                        "$set": {
                            "confirmation_context": {
                                "status": response.status,
                                "product": response.product_name,
                                "product_category": response.product_category,
                                "quantity": response.quantity,
                                "supplier_type": response.supplier_type,
                                "brand": response.brand,
                                "model": response.model,
                                "description": response.description,
                                "delivery_location": response.delivery_location,
                                "preferred_delivery_timeline": response.preferred_delivery_timeline,
                                "supplier_list_name": response.supplier_list_name
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

    async def process_response(self, ozil_message: Dict[str, Any]):
        """Process response from LLM and dispatch to relevant agent."""
        await self.ozil_client.send_message(
            ozil_message=ozil_message
        )