from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Optional

class RFQResponse(BaseModel):
    """Parser for RFQ responses"""
    response: str = Field(description="Response to send to user")
    ready_for_rfq: bool = Field(description="Whether to create RFQ")
    status: str = Field(description="Current collection stage")
    
    # Required fields
    product: Optional[str] = Field(None, description="Product name/type")
    quantity: Optional[int] = Field(None, description="Quantity requested")
    supplier_type: Optional[str] = Field(None, description="private/public/both")
    
    # Optional fields
    brand: Optional[str] = Field(None, description="Brand preference")
    model: Optional[str] = Field(None, description="Model details") 
    description: Optional[str] = Field(None, description="Product description")
    delivery_location: Optional[str] = Field(None, description="Delivery address")
    delivery_timeline: Optional[str] = Field(None, description="Delivery timeline")
    supplier_list: Optional[str] = Field(None, description="Supplier list name")

    def is_ready(self) -> bool:
        """Check if required fields are complete"""
        return all([
            self.product,
            self.quantity,
            self.supplier_type in ['private', 'public', 'both']
        ])

class RFQOutputParser(PydanticOutputParser):
    def __init__(self):
        super().__init__(pydantic_object=RFQResponse)
    
    def get_format_instructions(self) -> str:
        return """Parse the conversation and return a JSON object with:
{
    "response": "Your response to the user",
    "ready_for_rfq": true/false,
    "status": "current_stage",
    "product": "product_name",
    "quantity": number,
    "supplier_type": "private/public/both",
    "brand": "brand_name",
    "model": "model_details",
    "description": "product_description",
    "delivery_location": "delivery_address",
    "delivery_timeline": "delivery_requirements",
    "supplier_list": "supplier_list_name"
}"""