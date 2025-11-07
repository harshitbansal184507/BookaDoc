from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date, time
from enum import Enum
import uuid


class AppointmentStatus(str, Enum):
    """Appointment status enum."""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AppointmentRequest(BaseModel):
    """Initial appointment request from user."""
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: str = Field(..., min_length=10, max_length=15)
    patient_email: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)
    preferred_date: Optional[date] = None
    preferred_time: Optional[str] = None  # e.g., "morning", "afternoon", "evening"
    doctor_preference: Optional[str] = None
    
    @validator('patient_phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        # Remove spaces and dashes
        cleaned = v.replace(" ", "").replace("-", "")
        if not cleaned.isdigit():
            raise ValueError("Phone number must contain only digits")
        if len(cleaned) < 10:
            raise ValueError("Phone number must be at least 10 digits")
        return cleaned


class AppointmentSlot(BaseModel):
    """Available appointment time slot."""
    slot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: date
    start_time: time
    end_time: time
    doctor_name: Optional[str] = "Dr. Smith"
    doctor_id: str 
    is_available: bool = True
    
    def __str__(self):
        return f"{self.date.strftime('%B %d, %Y')} at {self.start_time.strftime('%I:%M %p')}"


class Appointment(BaseModel):
    """Complete appointment record."""
    appointment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Patient Information
    patient_name: str
    patient_phone: str
    patient_email: Optional[str] = None
    
    # Appointment Details
    appointment_date: date
    appointment_time: time
    duration_minutes: int = 30
    doctor_name: str = "Dr. Smith"
    doctor_id: str 
    reason: Optional[str] = None
    
    # Status
    status: AppointmentStatus = AppointmentStatus.PENDING
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None
    conversation_id: Optional[str] = None
    
    # Notes
    notes: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat()
        }
    
    def to_readable_string(self) -> str:
        """Convert appointment to human-readable string."""
        return (
            f"Appointment for {self.patient_name} "
            f"on {self.appointment_date.strftime('%B %d, %Y')} "
            f"at {self.appointment_time.strftime('%I:%M %p')} "
            f"with {self.doctor_name}"
        )


class AppointmentUpdate(BaseModel):
    """Model for updating appointment."""
    status: Optional[AppointmentStatus] = None
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    notes: Optional[str] = None
    confirmed_at: Optional[datetime] = None


class AppointmentResponse(BaseModel):
    """API response for appointment operations."""
    success: bool
    message: str
    appointment: Optional[Appointment] = None
    error: Optional[str] = None