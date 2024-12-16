from typing import Dict, Any
import aiohttp
from configs.settings import Settings
from configs.logger import logger
from pymongo.database import Database

class DianaHttpClient:
    def __init__(self, settings: Settings, db: Database = None):
        self.base_url = settings.DIANA_SERVICE_URL
        self.db = db
        
    async def initiate_whatsapp_inquiry(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send WhatsApp inquiry request to Diana service"""
        
        logger.info(f"Sending message to Diana service: {message}\n")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/whatsapp/inquiry/initiate",
                    json=message,
                ) as response:
                    try:
                        response_data = await response.json()
                    except aiohttp.ContentTypeError:
                        # Handle non-JSON response
                        error_text = await response.text()
                        logger.error(f"Server returned non-JSON response: {error_text}")
                        raise Exception(f"Server error: {error_text}")
                    
                    logger.info(f"Diana service response: {response_data}\n")
                    if response.status != 200:
                        raise Exception(f"Failed to call Diana service: {response.status}")
                    return response_data.get("data", {})
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error occurred while calling Diana service: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error calling Diana service: {str(e)}")
            raise
        
    async def initiate_order_inquiry(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send order inquiry request to Diana service"""
        
        logger.info(f"Sending order inquiry to Diana service: {message}\n")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/whatsapp/order/initiate",
                    json=message,
                ) as response:
                    try:
                        response_data = await response.json()
                    except aiohttp.ContentTypeError:
                        # Handle non-JSON response
                        error_text = await response.text()
                        logger.error(f"Server returned non-JSON response: {error_text}")
                        raise Exception(f"Server error: {error_text}")
                    
                    logger.info(f"Diana service order response: {response_data}\n")
                    if response.status != 200:
                        raise Exception(f"Failed to call Diana service: {response.status}")
                    return response_data.get("data", {})
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error occurred while calling Diana order service: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error calling Diana order service: {str(e)}")
            raise

    async def process_whatsapp_inquiry(self, diana_message: Dict[str, Any]) -> Dict[str, Any]:
        """Process WhatsApp inquiry request with user data"""
        follow_up_diana_conversation_id = None
        if diana_message.get("to_order"):
            conversation_link = await self.db.diana_conversation_links.find_one_and_delete(
                {"ayla_conversation_id": diana_message.get("user_id")}
            )
            follow_up_diana_conversation_id = conversation_link.get("follow_up_diana_conversation_id") if conversation_link else None           

            order_message = { # CH9db4b238618e4b98be1d5b62dd20967f
                "follow_up_diana_conversation_id": follow_up_diana_conversation_id,
                "user_whatsapp_phone_number": diana_message.get("user_whatsapp_phone_number", "+14177398109"),
                "user_additional_instructions": diana_message.get("user_additional_instructions", "I want to Place an order for the given medicine/medicines."),
            }
            return await self.initiate_order_inquiry(order_message)
        else:
            inquiry_message = {
                "user_id": diana_message.get("user_id"),
                "user_name": diana_message.get("user_name"),
                "user_address": diana_message.get("user_address"),
                "user_whatsapp_phone_number": diana_message.get("user_whatsapp_phone_number"),
                "user_phone_number": diana_message.get("user_phone_number", "+14177398109"),
                "ayla_conversation_id": diana_message.get("ayla_conversation_id"),
                "medicine_names": diana_message["medicine_names"]
            }
            
            return await self.initiate_whatsapp_inquiry(inquiry_message)