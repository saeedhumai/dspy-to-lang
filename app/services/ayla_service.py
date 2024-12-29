from datetime import datetime, UTC
from typing import Dict, Optional
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from app.chains.rfq_chain import RFQChain
from app.core.socket_manager import socket_manager
import logging
import aiohttp

logger = logging.getLogger(__name__)

class AylaService:
    def __init__(self, db: AsyncIOMotorClient, settings: Settings):
        self.db = db
        self.settings = settings
        self.rfq_chain = RFQChain()

    async def get_active_conversation(self, user_id: str) -> Optional[Dict]:
        """Get most recent incomplete conversation"""
        return await self.db.conversations.find_one({
            "user_id": user_id,
            "status": "active"
        }, sort=[("created_at", -1)])

    async def create_conversation(self, user_id: str) -> str:
        """Create new conversation"""
        result = await self.db.conversations.insert_one({
            "user_id": user_id,
            "status": "active",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "messages": [],
            "context": {
                "status": "start",
                "product": None,
                "quantity": None,
                "supplier_type": None,
                "brand": None,
                "model": None,
                "description": None,
                "delivery_location": None,
                "delivery_timeline": None,
                "supplier_list": None
            }
        })
        return str(result.inserted_id)

    async def save_message(self, conversation_id: str, content: str, sender: str):
        """Save message to conversation history"""
        await self.db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {
                "$push": {"messages": {
                    "content": content,
                    "sender": sender,
                    "timestamp": datetime.now(UTC)
                }},
                "$set": {"updated_at": datetime.now(UTC)}
            }
        )

    async def handle_message(self, user_id: str, message: str, provider: str = "openai"):
        """Process incoming message"""
        try:
            # Get or create conversation
            conversation = await self.get_active_conversation(user_id)
            if not conversation:
                conversation_id = await self.create_conversation(user_id)
                conversation = await self.db.conversations.find_one(
                    {"_id": ObjectId(conversation_id)}
                )
            else:
                conversation_id = str(conversation["_id"])

            # Save user message
            await self.save_message(conversation_id, message, "user")

            # Format chat history
            chat_history = [
                {
                    "role": msg["sender"],
                    "content": msg["content"]
                }
                for msg in conversation["messages"]
            ]

            # Process with LangChain
            response = await self.rfq_chain.process(
                input_text=message,
                chat_history=chat_history,
                context=conversation["context"]
            )

            # Save AI response
            await self.save_message(conversation_id, response.response, "ai")

            if response.to_rfq:
                # Update conversation as complete
                await self.db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": {
                        "status": "complete",
                        "completed_at": datetime.now(UTC),
                        "context": response.dict()
                    }}
                )

                # Create RFQ
                await self.create_rfq(user_id, response)

            else:
                # Update context
                await self.db.conversations.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": {"context": response.dict()}}
                )

            # Send response to user
            await socket_manager.send_message(
                user_id,
                {
                    "type": "text",
                    "content": response.response,
                    "sender": "ai"
                }
            )

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await socket_manager.send_message(
                user_id,
                {
                    "type": "error",
                    "content": "An error occurred processing your request.",
                    "sender": "system"
                }
            )

    async def create_rfq(self, user_id: str, response: Dict):
        """Create RFQ in backend system"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.settings.OZIL_SERVICE_URL}/rfqs",
                json={
                    "user_id": user_id,
                    **response.dict()
                }
            ) as resp:
                if resp.status != 201:
                    raise Exception("Failed to create RFQ")