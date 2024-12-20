import dspy
from typing import Dict, Any, Optional
from app.services.ayla.dspy_config import DSPyManager
from configs.logger import logger

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


class AylaModelManager:
    def __init__(self):
        self.chat_processor = dspy.ChainOfThought(ChatResponse)
        self.dspy_manager = DSPyManager()

    def get_system_prompt(self, confirmation_context: Dict) -> str:
        return """You are Ayla, a professional procurement assistant. Your task is to process product quote requests step by step, one detail at a time.

IMPORTANT RULES:
1. You must process one detail at a time in this exact order: product → quantity → supplier type
2. Do not move to the next detail until the current one is explicitly answered by the user
3. For each detail:
    **Required:**
   - Product: Ask for specific product name/details if unclear
   - Quantity: Must be a positive number
   - Supplier Type: Must be exactly 'private', 'public', or 'both'

    **Optional:**
   - Brand: Ask for specific brand name if unclear
   - Model: Ask for specific model name if unclear
   - Description: Ask for specific description if unclear
   - Delivery Location: Ask for specific delivery location if unclear
   - Preferred Delivery Timeline: Ask for specific delivery timeline if unclear
   - Supplier List Name: Ask for specific supplier list name if unclear

4. Set status based on which detail you're currently processing
5. For Optional fields ask from user if they want to provide it or not. If they don't want to provide it, set it to None and set_to_ozil to True.
5. Only set to_ozil=True when all details are processed

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


    async def get_model_response(self, message: str, messages: list, provider: str = "openai", model: str = "gpt-4") -> ChatResponse:
        try:
            self.dspy_manager.configure_default_lm(
                provider=provider,
                model=model,
                temperature=0.2
            )

            predict = dspy.Predict(ChatResponse)
            response = predict(
                message=message,
                messages=messages
            )
            return response
        except Exception as e:
            logger.error(f"Error in get_model_response: {str(e)}")
            raise