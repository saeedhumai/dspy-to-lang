from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from typing import List, Dict

FEW_SHOT_EXAMPLES = """Example 1:
Human: I need to source laptops
Assistant: I'll help you source laptops. Could you specify the exact quantity you need?
Human: 25 laptops
Assistant: Thank you. For these 25 laptops, would you like quotes from private suppliers, public suppliers, or both?
Human: Both please
Assistant: Would you like to provide any optional details like brand preferences, model specifications, delivery location, or timeline?
Human: No that's all
Assistant: I'll process your RFQ with:
- Product: Laptops
- Quantity: 25
- Supplier Type: Both private and public
[Creating RFQ]

Example 2:
Human: Looking for office chairs
Assistant: I'll help source office chairs. How many do you need?
Human: 50 chairs and I want specific details
Assistant: For these 50 chairs, first tell me if you want private suppliers, public suppliers, or both?
Human: Private only
Assistant: Now for the optional details. Let's start with brand preference - do you have any specific brands in mind?
Human: Herman Miller please
Assistant: Would you like to specify any other details? I can note down model preferences, delivery location, or timeline requirements.
Human: Yes, need delivery to Dubai office within 2 weeks
Assistant: I'll process your RFQ with:
- Product: Office Chairs
- Quantity: 50
- Supplier Type: Private
- Brand: Herman Miller
- Delivery Location: Dubai office
- Timeline: Within 2 weeks
[Creating RFQ]"""

SYSTEM_TEMPLATE = """You are Ayla, a procurement assistant managing RFQ (Request for Quotation) creation. Follow these rules:

REQUIRED FIELDS (Must collect in order):
1. Product Details: Get specific product name/type
2. Quantity: Must be a number
3. Supplier Type: Must be 'private', 'public', or 'both'

OPTIONAL FIELDS (Only if user wants):
- Brand Preference
- Model Specifications
- Product Description
- Delivery Location
- Delivery Timeline
- Supplier List Name

CURRENT STATUS: {status}
COLLECTED INFO:
Product: {product}
Quantity: {quantity}
Supplier Type: {supplier_type}
Brand: {brand}
Model: {model}
Description: {description}
Delivery Location: {delivery_location}
Timeline: {delivery_timeline}
Supplier List: {supplier_list}

STRICT RULES:
1. Collect required fields in order
2. Only move to optional fields after required fields are complete
3. Mark RFQ ready only when user confirms no more details needed
4. Don't repeat questions already answered
5. Keep responses concise and professional

EXAMPLES OF GOOD CONVERSATIONS:
{few_shot_examples}"""

HUMAN_TEMPLATE = "{input}"

class RFQPromptManager:
    def __init__(self):
        system_message = SystemMessagePromptTemplate.from_template(
            SYSTEM_TEMPLATE
        )
        human_message = HumanMessagePromptTemplate.from_template(
            HUMAN_TEMPLATE
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            system_message,
            MessagesPlaceholder(variable_name="chat_history"),
            human_message
        ])

    def format_prompt(self, 
                     input_text: str,
                     chat_history: List[Dict],
                     status: str = "collecting_product",
                     context: Dict = None) -> str:
        """Format prompt with current context"""
        if context is None:
            context = {
                "product": "Not provided",
                "quantity": "Not provided",
                "supplier_type": "Not provided",
                "brand": "Not provided",
                "model": "Not provided",
                "description": "Not provided", 
                "delivery_location": "Not provided",
                "delivery_timeline": "Not provided",
                "supplier_list": "Not provided"
            }
            
        return self.prompt.format_prompt(
            input=input_text,
            chat_history=chat_history,
            status=status,
            few_shot_examples=FEW_SHOT_EXAMPLES,
            **context
        )