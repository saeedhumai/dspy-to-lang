from pydantic import BaseModel
from enum import Enum
from typing import List, Optional

class MessageType(str, Enum):
    INQUIRY = "inquiry"
    ORDER = "order"
    FOLLOWUP = "followup"

class DianaMessage(BaseModel):
    conversation_id: str
    message_content: str
    message_type: MessageType
    medicine_names: List[str]
    user_name: Optional[str]
    address: Optional[str]