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
from app.core.ozil_client import OzilClient
from app.services.ayla.ayla_model_manager import AylaModelManager

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
        self.ozil_client = OzilClient(settings, socket_manager)
        self.model_manager = AylaModelManager()

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

    async def send_welcome_message(self, user_id: str, provider: str = "openai", model: str = "gpt-4"):
        """Send welcome message when user connects"""
               
        try:
            # Get active conversation or create new one
            conversation = await self.get_active_conversation(user_id)
            
            if not conversation:
                conversation_id = await self.create_new_conversation(user_id)
                conversation = await self.db.conversations.find_one({"_id": ObjectId(conversation_id)})
            else:
                conversation_id = str(conversation["_id"])


            # Format conversation history for model
            messages = self._format_conversation_history(conversation)

            response = await self.model_manager.get_model_response(
                message="",
                messages=messages,
                provider=provider,
                model=model
            )
            
            # Create a new conversation for the welcome message
            conversation_id = await self.create_new_conversation(user_id)
            
            # # Save the welcome message
            # await self.save_message(
            #     conversation_id=conversation_id,
            #     content=response.ayla_response,
            #     sender="ai",
            #     type="text"
            # )
            
            await self.socket_manager.send_message(
                user_id,
                {
                    "done": True,
                    "type": "text",
                    "content": response.ayla_response,
                    "sender": "ai"
                }
            )
        except Exception as e:
            logger.error(f"Error sending welcome message: {str(e)}")

    async def handle_websocket_request(self, sid: str, request: AylaAgentRequest):
        """Handle chat request via Socket.IO using DSPy"""
        logger.info(f"Processing request for user_id: {request.user_id}")
        
        # Get active conversation or create new one
        conversation = await self.get_active_conversation(request.user_id)
        
        if not conversation:
            conversation_id = await self.create_new_conversation(request.user_id)
            conversation = await self.db.conversations.find_one({"_id": ObjectId(conversation_id)})
        else:
            conversation_id = str(conversation["_id"])

        # Save user message
        await self.save_message(
            conversation_id=conversation_id,
            content=request.message,
            sender="user",
            type="text"
        )

        # Format conversation history for model
        messages = self._format_conversation_history(conversation)
        
        try:
            response = await self.model_manager.get_model_response(
                message=request.message,
                messages=messages,
                provider=request.provider,
                model=request.model
            )
            
            # Save AI response
            await self.save_message(
                conversation_id=conversation_id,
                content=response.ayla_response,
                sender="ai",
                type="text"
            )
            
            if response.to_ozil and response.status == "complete":
                await self._handle_complete_conversation(conversation_id, response, request)
            else:
                await self._handle_ongoing_conversation(conversation_id, response, request)
            
        except Exception as e:
            await self._handle_error(conversation_id, request.user_id, str(e))

    async def _handle_complete_conversation(self, conversation_id: str, response: Any, request: AylaAgentRequest):
        """Handle completed conversation flow"""
        # Update conversation status
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

        logger.info("Calling Ozil Process Response Method")

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

        # Prepare and send to Ozil
        ozil_message = self._prepare_ozil_message(response, request)
        await self.process_response(ozil_message)

    async def _handle_ongoing_conversation(self, conversation_id: str, response: Any, request: AylaAgentRequest):
        """Handle ongoing conversation flow"""
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

    async def _handle_error(self, conversation_id: str, user_id: str, error_message: str):
        """Handle error cases"""
        logger.error(f"Error in handle_websocket_request: {error_message}")
        await self.save_message(
            conversation_id=conversation_id,
            content=f"An error occurred while processing your request: {error_message}",
            sender="ai",
            type="text"
        )
        await self.socket_manager.send_message(
            user_id,
            {"done": True, "type": "text", "content": "An error occurred while processing your request.", "sender": "ai"}
        )

    def _format_conversation_history(self, conversation: Dict) -> list:
        """Format conversation history for the model"""
        messages = [
            {
                "role": "system",
                "content": self.model_manager.get_system_prompt(conversation.get("confirmation_context", {}))
            }
        ]
        
        if "messages" in conversation:
            for msg in conversation["messages"]:
                role = "assistant" if msg["sender"] == "ai" else "user"
                messages.append({
                    "role": role,
                    "content": msg["content"]
                })
        
        return messages

    def _prepare_ozil_message(self, response: Any, request: AylaAgentRequest) -> Dict:
        """Prepare message for Ozil service"""
        response_dict = response.toDict()
        response_dict.update({
            "user_id": request.user_id,
            "language": request.language if request.language else "en",
            "provider": request.provider if request.provider else "openai",
            "model": request.model if request.model else "gpt-4"
        })
        return response_dict

    async def process_response(self, ozil_message: Dict[str, Any]):
        """Process response from LLM and dispatch to Ozil."""
        await self.ozil_client.send_message(ozil_message=ozil_message)