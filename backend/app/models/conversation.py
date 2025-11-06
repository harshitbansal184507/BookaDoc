from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class AgentType(str, Enum):
    """Types of agents in the system."""
    ORCHESTRATOR = "orchestrator"
    RECEPTIONIST = "receptionist"
    SCHEDULER = "scheduler"
    CONFIRMATION = "confirmation"
    SYSTEM = "system"


class ConversationMessage(BaseModel):
    """Single message in a conversation."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user", "assistant", "system"
    content: str
    agent_type: Optional[AgentType] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationState(str, Enum):
    """Current state of the conversation."""
    INITIATED = "initiated"
    GATHERING_INFO = "gathering_info"
    CHECKING_AVAILABILITY = "checking_availability"
    PROPOSING_SLOTS = "proposing_slots"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversationContext(BaseModel):
    """Complete conversation context and state."""
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # State
    state: ConversationState = ConversationState.INITIATED
    current_agent: AgentType = AgentType.RECEPTIONIST
    
    # Messages
    messages: List[ConversationMessage] = []
    
    # Extracted Information
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    reason: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    doctor_preference: Optional[str] = None
    
    # Proposed Slots
    proposed_slots: List[Dict[str, Any]] = []
    selected_slot_id: Optional[str] = None
    
    # Appointment
    appointment_id: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Tracking
    attempt_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_message(self, role: str, content: str, agent_type: Optional[AgentType] = None):
        """Add a message to the conversation."""
        message = ConversationMessage(
            role=role,
            content=content,
            agent_type=agent_type or self.current_agent
        )
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history in simple format for LLM."""
        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in self.messages
        ]
    
    def has_required_info(self) -> bool:
        """Check if all required information is collected."""
        return all([
            self.patient_name,
            self.patient_phone,
            self.reason
        ])
    
    def to_appointment_request(self) -> Dict[str, Any]:
        """Convert collected info to appointment request."""
        return {
            "patient_name": self.patient_name,
            "patient_phone": self.patient_phone,
            "patient_email": self.patient_email,
            "reason": self.reason,
            "preferred_date": self.preferred_date,
            "preferred_time": self.preferred_time,
            "doctor_preference": self.doctor_preference
        }


class WebSocketMessage(BaseModel):
    """WebSocket message format."""
    type: str  # "user_message", "agent_message", "status_update", "slot_proposal", "confirmation"
    conversation_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }