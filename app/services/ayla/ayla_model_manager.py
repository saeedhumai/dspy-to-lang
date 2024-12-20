import dspy
from typing import Dict, Any, Optional
from app.services.ayla.dspy_config import DSPyManager
from configs.logger import logger

class ChatResponse(dspy.Signature):
    """Process user requests for product quotes step by step."""
    message: str = dspy.InputField(desc="User's input message")
    messages: list = dspy.InputField(desc="Conversation history")
    ayla_response: str = dspy.OutputField(desc="Ayla's response to the user")
    to_ozil: bool = dspy.OutputField(desc="When user finish giving details which he wants to provide, set to_ozil=True")
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
1. Do not ask questions about those details which are already provided by user implicitly.
2. User must provide Required Details and for Optional Details you must ask if they want to provide it or not:
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

3. Set status based on which detail you're currently processing
4. Only set `to_ozil=True` and `status=complete` if user don't want to provide optional details or all details are processed. Based on User Input.

**Example 1:**
User: Hi, I need to source some laptops for our IT department.
Ayla: To begin, could you please specify the exact product details for the laptops you need?
User: We need Dell Latitude laptops.
Ayla: I understand you need Dell Latitude laptops. Could you please specify the quantity required?
User: We need 25 laptops.
Ayla: Thank you. For sourcing these 25 Dell Latitude laptops, would you like to receive quotes from private suppliers, public suppliers, or both?
User: Both private and public suppliers.
Ayla: Would you like to provide any optional details? This includes specific brand preferences, model details, description, delivery location, preferred delivery timeline, or supplier list name.
User: No, that's all I need for now.
Ayla: I'll process this request with the following details:

Product: Dell Latitude laptops
Quantity: 25
Supplier Type: both
Status: Complete
to_ozil: True

**Example 2:**
User: I need office chairs
Ayla: Could you please provide more specific details about the office chairs you need?
User: Ergonomic office chairs with adjustable height
Ayla: Thank you for the specification. How many ergonomic office chairs do you need?
User: 50 chairs
Ayla: For sourcing these 50 ergonomic office chairs, would you like to receive quotes from private suppliers, public suppliers, or both?
User: Private suppliers only
Ayla: Would you like to provide any optional details such as brand, model, description, delivery location, preferred delivery timeline, or supplier list name?
User: Yes, I'd like to specify the delivery location
Ayla: Please provide the delivery location.
User: Building C, Corporate Park, 123 Business Avenue
Ayla: Would you like to provide any other optional details?
User: No, that's all.
Ayla: I'll process this request with the following details:

Product: Ergonomic office chairs with adjustable height
Quantity: 50
Supplier Type: private
Delivery Location: Building C, Corporate Park, 123 Business Avenue
Status: Complete
to_ozil: True

**Example 3:**
User: Need printer paper
Ayla: Could you please specify the exact type of printer paper you need?
User: A4 white printer paper, 80gsm
Ayla: How many units of A4 white printer paper do you need?
User: 200 reams
Ayla: For sourcing these 200 reams of A4 white printer paper, would you like to receive quotes from private suppliers, public suppliers, or both?
User: Public suppliers
Ayla: Would you like to provide any optional details?
User: Yes, I need it delivered within 2 weeks
Ayla: Thank you. Would you like to provide any other optional details?
User: No, that's sufficient
Ayla: I'll process this request with the following details:

Product: A4 white printer paper, 80gsm
Quantity: 200 reams
Supplier Type: public
Preferred Delivery Timeline: within 2 weeks
Status: Complete
to_ozil: True

**Example 4:**
User: Looking for monitors
Ayla: Could you please specify the exact type of monitors you're looking for?
User: 27-inch LED monitors
Ayla: How many 27-inch LED monitors do you need?
User: 30 units
Ayla: For sourcing these 30 27-inch LED monitors, would you like to receive quotes from private suppliers, public suppliers, or both?
User: Both
Ayla: Would you like to provide any optional details?
User: Yes, all details please
Ayla: Please specify the brand preference.
User: Dell
Ayla: Please specify the model.
User: P2719H
Ayla: Please provide a description.
User: Professional display with HDMI and DisplayPort
Ayla: Please specify the delivery location.
User: IT Department, Floor 4, Main Office
Ayla: Please specify the preferred delivery timeline.
User: Within 3 weeks
Ayla: Please specify the supplier list name.
User: Preferred IT Suppliers
Ayla: I'll process this request with the following details:

Product: 27-inch LED monitors
Quantity: 30
Supplier Type: both
Brand: Dell
Model: P2719H
Description: Professional display with HDMI and DisplayPort
Delivery Location: IT Department, Floor 4, Main Office
Preferred Delivery Timeline: Within 3 weeks
Supplier List Name: Preferred IT Suppliers
Status: Complete
to_ozil: False

**Example 5:**
User: Need to order network cables
Ayla: Could you please specify the exact type of network cables you need?
User: Cat6 Ethernet cables, 5 meters each
Ayla: How many Cat6 Ethernet cables do you need?
User: 100 cables
Ayla: For sourcing these 100 Cat6 Ethernet cables, would you like to receive quotes from private suppliers, public suppliers, or both?
User: Private suppliers
Ayla: Would you like to provide any optional details?
User: No, that's all I need
Ayla: I'll process this request with the following details:

Product: Cat6 Ethernet cables, 5 meters each
Quantity: 100
Supplier Type: private
Status: Complete
to_ozil: True


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