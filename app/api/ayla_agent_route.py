from fastapi import APIRouter, Depends
from app.schemas.ayla_agent_schemas import PharmacyResponse, OrderResponse, DianaConversationLink
from langchain_mongodb import MongoDBChatMessageHistory
from app.services.ayla.ayla_agent import AylaAgentService
from app.dependencies.depends import get_ayla_agent, get_db
from app.socket_manger.socket_manager_utils import get_socket_manager
from pymongo.database import Database
from configs.logger import logger
from fastapi import HTTPException

router = APIRouter(tags=["AYLA"], prefix="/api")

@router.post("/pharmacy/response")
async def handle_pharmacy_response(
    response: PharmacyResponse, 
    ayla_service: AylaAgentService = Depends(get_ayla_agent),
    db: Database = Depends(get_db)
):
    """Handle incoming responses from pharmacies via Diana service"""
    try:
        response = response.model_dump()
        logger.info(f"Received pharmacy response: {response}")
        
        # Check if a Diana conversation link already exists for the user_id
        existing_link = await db.diana_conversation_links.find_one({"user_id": response['user_id']})
        if existing_link:
            logger.info(f"Diana conversation link already exists for user_id: {response['user_id']}")
            return {"status": "success", "message": "Thank You for Your reply. I have bought medicine."}
        else:
            # Store the Diana conversation link
            conversation_link = DianaConversationLink(
                user_id=response['user_id'],
                ayla_conversation_id=response['user_id'],
                follow_up_diana_conversation_id=response['conversation_id'],
            )
            logger.info(f"Storing Diana conversation link: {conversation_link}")
            await db.diana_conversation_links.insert_one(conversation_link.model_dump())
        
        # Build the medicines string, filtering out entries with None values
        medicines_str = "\n".join([
            f"Medicine: {medicine['name']}, Price: {medicine['price']}, Quantity: {medicine['quantity_available']}, Measurement: {medicine['price_measurement']}, Available: {medicine['available']}"
            for medicine in response['medicines']
            if all(medicine[key] is not None for key in ['name', 'price', 'quantity_available', 'price_measurement', 'available'])
        ])
        
        # Dynamically build the content
        content_parts = []
        
        if response.get('pharmacy_name') is not None:
            content_parts.append(f"Do you want to buy medicines from {response['pharmacy_name']}? Reply with 'yes' or 'no'.")
        
        if response.get('pharmacy_phone') is not None:
            content_parts.append(f"Phone: {response['pharmacy_phone']}")
        
        if response.get('conversation_summary') is not None:
            content_parts.append(f"Conversation Summary: {response['conversation_summary']}")
        
        if medicines_str:
            content_parts.append(f"Medicines: {medicines_str}")
        
        # Join the content parts with newlines
        content = "\n".join(content_parts)

        logger.info(f"Generated content: {content}")

        logger.info(f"Saving message to MongoDB: {content}")
        
        # Save to conversation history
        await ayla_service.save_message(
            conversation_id=response['user_id'],
            content=content,
            sender="ai",
            type="text",
            products=[]
        )
        logger.info(f"Saved message to MongoDB: {content}")
        
        try:
            # Get MongoDB chat history instance and save message
            chat_history = MongoDBChatMessageHistory(
                connection_string = ayla_service.settings.MONGODB_URL,
                database_name=ayla_service.settings.MONGODB_DB,
                collection_name="chat_history",
                session_id=response['user_id']
            )
            chat_history.add_ai_message(content)
        except Exception as e:
            logger.error(f"Error saving to chat history: {str(e)}")
            # Continue execution even if chat history fails
        socket_manager = get_socket_manager()
        # Send websocket message
        await socket_manager.send_message(
            conversation_id=response['user_id'],
            message={
                "done": True,
                "type": "text",
                "content": content,
                "sender": "ai"
            }
        )
        return {"status": "success", "message": "Response forwarded to user"}
        
    except Exception as e:
        logger.error(f"Error processing pharmacy response: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order/response")
async def handle_order_response(
    response: OrderResponse,
    ayla_service: AylaAgentService = Depends(get_ayla_agent)
):
    """Handle incoming responses from pharmacies via Diana service"""
    response = response.model_dump()
    # Format order response content
    status_text = "successful" if response['order_status'] else "unsuccessful"
    content = f"Order {status_text}:\n{response['conversation_summary']}"
    
    # Save to both conversation history tables
    await ayla_service.save_message(
        conversation_id=response['user_id'],
        content=content,
        sender="ai",
        type="text"
    )

    chat_history = MongoDBChatMessageHistory(
        connection_string = ayla_service.settings.MONGODB_URL,
        database_name=ayla_service.settings.MONGODB_DB,
        collection_name="chat_history",
        session_id=response['user_id']
    )
    
    # Get MongoDB chat history instance and save message
    chat_history.add_ai_message(content)
    socket_manager = get_socket_manager()
    # Send websocket message
    await socket_manager.send_message(
        conversation_id=response['user_id'],
        message={
            "done": True,
            "type": "text",
            "content": content,
            "sender": "ai"
        }
    )
    return {"status": "success", "message": "Response forwarded to user"}
