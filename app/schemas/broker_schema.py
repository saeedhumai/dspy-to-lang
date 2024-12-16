from dataclasses import dataclass
from typing import Dict
from enum import Enum

class AgentType(Enum):
    DIANA = "diana"
    DIMA = "dima"

@dataclass
class AgentMessage:
    agent_type: AgentType
    action: str
    payload: Dict
    conversation_id: str
