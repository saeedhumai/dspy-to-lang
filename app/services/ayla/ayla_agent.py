from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mongodb import MongoDBChatMessageHistory
from langchain_openai import ChatOpenAI
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
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
from app.schemas.broker_schema import AgentType
from app.core.diana_http_client import DianaHttpClient
from app.socket_manger.socket_manager import SocketManager
import socketio
import asyncio
from typing import Optional

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
        self.json_output_parser = JsonOutputParser()
        self.socket_manager = socket_manager

        # Initialize Ozil socket client at service level
        self.ozil_socket: Optional[socketio.AsyncClient] = None
        self.ozil_url = settings.OZIL_SERVICE_URL
        self.active_conversations: Dict[str, bool] = {}
        
        # Initialize the socket connection
        asyncio.create_task(self.initialize_ozil_socket())
        
        # Provider-specific model configurations
        self.provider_models = {
            "claude": {
                "models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
                "default": "claude-3-opus-20240229"
            },
            "gemini": {
                "models": ["gemini-1.5-pro", "gemini-exp-1121", "gemini-exp-1206", "gemini-1.5-flash", "gemini-1.5-flash-8b"],
                "default": "gemini-exp-1121"
            },
            "openai": {
                "models": ["gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
                "default": "gpt-4o"
            }
        }
        
        # Default provider recommendations per language
        self.recommended_providers = {
            "ar": ["claude", "gemini", "openai"],    # Arabic preference order
            "fa": ["gemini", "claude", "openai"],    # Persian preference order
            "en": ["openai", "claude", "gemini"],    # English preference order
        }

    def create_llm(self, language: str = "en", provider: str = "openai", model: str = "gpt-4o") -> BaseChatModel:
        """Create language-specific LLM instances from different providers"""
        # If no provider specified, use the first recommended provider for the language
        if not provider:
            provider = self.recommended_providers.get(language, ["openai"])[0]
        
        # Validate provider
        if provider not in self.provider_models:
            provider = "openai"  # Default fallback
            
        model_config = self.provider_models[provider]
        
        # Find the model based on the model variable
        model = model if model in model_config["models"] else model_config["default"]
        
        # Create the appropriate model instance based on provider
        if provider == "claude":
            return ChatAnthropic(
                temperature=0.7,
                model=model,
                api_key=self.settings.ANTHROPIC_API_KEY
            )
        elif provider == "gemini":
            return ChatGoogleGenerativeAI(
                temperature=0.7,
                model=model,
                api_key=self.settings.GOOGLE_API_KEY
            )
        else:  # openai
            return ChatOpenAI(
                temperature=0.7,
                model=model,
                api_key=self.settings.OPENAI_API_KEY
            )

    @property
    def llm(self) -> BaseChatModel:
        """Get LLM instance based on request parameters"""
        # Get values from instance variables, set by handle_websocket_request
        language = getattr(self, '_language', 'en')
        provider = getattr(self, '_provider', 'openai')
        model = getattr(self, '_model', 'gpt-4o')
        return self.create_llm(language, provider, model)
    
    def _parse_result(self, result: str) -> Dict[str, any]:
        try:
            inner_json = self.json_output_parser.parse(result)
            return inner_json
        except Exception as e:
            logger.info(f"Error parsing LLM response: {e}")

    def create_chat_prompt(self, system_prompt: str=None, image_url: str=None) -> ChatPromptTemplate:

        """Create specialized chat prompt template for medicine/supplement consultation"""
        system_template = system_prompt or  """You are Ayla, an intelligent AI agent tasked with assisting users with their medicine needs. Your role involves processing user queries and generating responses only related to medicine.

1. **Understanding User Queries:**
   - Always confirm the user's intent: They want to search for a medicine or supplement through WhatsApp or Website.
   - If the user uploads a prescription or a photo of medicine package. Analyze this image and do the following:
    1. If it's a prescription, extract the medicine names list of strings format.
    2. If it's a medicine package, or prescription, identify the medicine name.
    3. If you can't identify the medicine name, just say "I couldn't identify the medicine name from the image."
"""

        system_template = system_template + """

## Document Content:
{document_content}

## User Name:
{name}

## User Address:
{address}

## Conversation Example:
User Query: "Search Panadol for me"
Ayla Response: ```json
{{
    "to_ozil": false,
    "ayla_response": "OK. Search Pharmacy Website or WhatsApp"
}}
```

User Query: "WhatsApp"
Ayla Response: ```json
{{
    "to_ozil": true,
    "ozil_message": "Search Panadol"
}}
```

User Query: "Website"
Ayla Response: ```json
{{
    "to_ozil": true,
    "ozil_message": "Search Panadol"
}}
```
"""

        human_message_content = []
        # Construct the human message based on whether image_url is provided
        
        if image_url:
            human_message_content.append({"type": "image_url", "image_url": {"url": "{image_url}"}})

        human_message_content.append(
            {"type": "text", "text": "{question}"}
        )
        return ChatPromptTemplate.from_messages([
            ("system", system_template),
            MessagesPlaceholder(variable_name="history"),
            ("human", human_message_content)
        ])

    async def save_message(self, conversation_id: str, content: str, sender: str, type: str = None, file_url: str = "undefined", products: list = []) -> None:
        """Save a message with optional metadata to the conversation history"""
        message_data = {
            "content": content,
            "sender": sender,
            "time": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
            "file_url": file_url,
            "type": type,
            "products": products
        } if sender == "ai" else {
            "content": content,
            "sender": sender,
            "time": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
            "type": type,
            "file_url": file_url
        }
        
        await self.db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$push": {"messages": message_data},
                "$setOnInsert": {
                    "created_at": datetime.now(UTC)
                },
                "$set": {"updated_at": datetime.now(UTC)}
            },
            upsert=True
        )

    def get_mongodb_history(self, conversation_id: str):
        """Get or create MongoDB chat history instance"""
        try:
            return MongoDBChatMessageHistory(
                connection_string = self.settings.MONGODB_URL,
                database_name=self.settings.MONGODB_DB,
                collection_name="chat_history",
                session_id=conversation_id
            )
        except Exception as e:
            logger.error(f"MongoDB connection error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to connect to MongoDB: {str(e)}")

    def setup_conversation_chain(self, system_prompt: str = None, image_url: str = None):
        """Set up the conversation chain for medicine/supplement consultation"""
        prompt = self.create_chat_prompt(system_prompt, image_url)
        
        chain = (
            RunnablePassthrough()
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        return RunnableWithMessageHistory(
            chain,
            self.get_mongodb_history,
            input_messages_key="question",
            history_messages_key="history",
            output_messages_key="output"
        )


    async def handle_websocket_request(self, sid: str, request: AylaAgentRequest):
        """Handle chat request via Socket.IO"""
        # Set the language, provider and model from request
        self._language = getattr(request, 'language', 'en')
        self._provider = getattr(request, 'provider', 'openai')
        self._model = getattr(request, 'model', 'gpt-4o')
        
        logger.info(f"Processing request for user: {request.name} with address: {request.address} : user_id: {request.conversation_id}")
        type = "text"
        transcribed_text = ""
        # Process document if provided
        document_content = ""
        if request.document_url:
            type = "file"
            try:
                if request.document_url.endswith(('.png', '.jpg', '.jpeg')):
                    type = "image"
                    request.image_url = request.document_url
                else:
                    document_content = await self.document_processor.process_document(request.document_url)
            except Exception as e:
                logger.error(f"Document processing error: {str(e)}")
        
        if request.image_url:
            type = "image"
        
        if request.audio_url:
            type = "voice"
            try:
                transcribed_text = await self.audio_processor.transcribe_audio(request.audio_url)
            except Exception as e:
                logger.error(f"Error transcribing audio: {str(e)}")
         
        # Save human message
        await self.save_message(
            conversation_id=request.conversation_id,
            content=request.message,
            file_url=request.image_url or request.audio_url or request.document_url or "",
            sender="human",
            type=type
        )
        
        conversation_chain = self.setup_conversation_chain(request.system_prompt, request.image_url)
        query_to_send = (request.message or "") + " " + (transcribed_text or "")
        try:
            parameters = {
                "question": query_to_send,
                "document_content": document_content,
                "image_url": request.image_url if request.image_url else "",  # Ensure empty string if None
                "name": request.name,
                "address": request.address
            }

            # Only include image_url in parameters if it exists
            if not parameters["image_url"]:
                parameters.pop("image_url")
            
            response = conversation_chain.invoke(
                parameters,
                config={"configurable": {"session_id": request.conversation_id}}
            )

            logger.info(f"LLM response: {response}")

            parsed_response = self._parse_result(response)

            if parsed_response["to_ozil"]:
                await self.process_response(parsed_response, request.conversation_id)
            else:
                await self.save_message(
                    conversation_id=request.conversation_id,
                    content=parsed_response["ayla_response"],
                    sender="ai",
                    type="text"
                )
                await self.socket_manager.send_message(
                    request.conversation_id,
                    {
                        "done": True,
                        "type": "text",
                        "content": parsed_response["ayla_response"],
                        "sender": "ai"
                    }
                )
                
            return
                
        except Exception as e:
                logger.error(f"Error updating parsed response: {str(e)}")
                await self.save_message(
                    conversation_id=request.conversation_id,
                    content=parsed_response["ayla_response"],
                    sender="ai",
                    type="text"
                )
                await self.socket_manager.send_message(
                    request.conversation_id,
                    {
                        "done": True,
                        "type": "text",
                        "content": parsed_response["ayla_response"],
                        "sender": "ai"
                    }
                )
                return



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
            # Add conversation to active conversations
            self.active_conversations[conversation_id] = True

            # Add necessary data for Ozil
            ozil_message = {
                "message": parsed_response.get("ozil_message", ""),
                "name": parsed_response.get("user_name", ""),
                "address": parsed_response.get("user_address", ""),
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
        
    async def cleanup_conversation(self, conversation_id: str):
        """Cleanup when a conversation is done"""
        if conversation_id in self.active_conversations:
            del self.active_conversations[conversation_id]