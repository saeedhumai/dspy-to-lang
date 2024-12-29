from pydantic import BaseModel
from typing import Optional, List, Literal

class AylaAgentRequest(BaseModel):
    message: Optional[str] = None
    user_id: Optional[str] = None
    language: Optional[str] = "en"  # Language code (ar, fa, en)
    provider: Optional[Literal["openai", "anthropic", "gemini"]] = "openai"
    model: Optional[str] = "gpt-4o-mini"  # Model options based on provider

    class Config:
        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                    },
                    {
                        "provider": "anthropic",
                        "model": "claude-3-opus-20240229",
                    },
                    {
                        "provider": "gemini",
                        "model": "gemini-1.5-pro",
                    }
                ]
            }
        }

class DianaConversationLink(BaseModel):
    user_id: str
    ayla_conversation_id: str
    follow_up_diana_conversation_id: str

class Medicine(BaseModel):
    name: str|None = None
    price: str|None = None
    quantity_available: int|None = None
    price_measurement: str|None = None
    available: bool|None = None

class PharmacyResponse(BaseModel):
    user_id: str|None = None
    conversation_id: str|None = None
    pharmacy_name: str|None = None
    pharmacy_phone: str|None = None
    conversation_summary: str|None = None
    medicines: List[Medicine]|None = None


class OrderResponse(BaseModel):
    user_id: str|None = None
    follow_up_diana_conversation_id: str|None = None
    order_conversation_id: str|None = None
    conversation_summary: str|None = None
    order_status: bool|None = None

