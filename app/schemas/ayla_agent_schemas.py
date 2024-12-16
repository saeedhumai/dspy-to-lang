from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class AylaAgentRequest(BaseModel):
    message: Optional[str] = None
    system_prompt: Optional[str] = None
    diana_prompt: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    document_url: Optional[str] = None # .pdf, .docx, .txt, etc.
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    conversation_id: Optional[str] = None
    language: Optional[str] = "en"  # Language code (ar, fa, en)
    provider: Optional[str] = "openai"  # LLM provider (claude, gemini, openai)
    model: Optional[str] = "gpt-4o"  # LLM model (gpt-4o, gemini-1.5-pro, claude-3-opus-20240229, etc.)

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

