from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import uuid


class Specialization(str, Enum):
    """Medical specializations."""
    GENERAL_PHYSICIAN = "General Physician"
    CARDIOLOGIST = "Cardiologist"
    DERMATOLOGIST = "Dermatologist"
    PEDIATRICIAN = "Pediatrician"
    ORTHOPEDIC = "Orthopedic"
    GYNECOLOGIST = "Gynecologist"
    ENT_SPECIALIST = "ENT Specialist"
    OPHTHALMOLOGIST = "Ophthalmologist"
    PSYCHIATRIST = "Psychiatrist"
    DENTIST = "Dentist"


class DoctorAvailability(BaseModel):
    """Doctor's availability schedule."""
    day_of_week: int  # 0=Monday, 6=Sunday
    start_time: str  # "09:00"
    end_time: str  # "17:00"
    is_available: bool = True


class Doctor(BaseModel):
    doctor_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=2, max_length=100)
    specialization: Specialization
    qualification: str  # e.g., "MBBS, MD"
    experience_years: int = Field(..., ge=0)
    
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Availability
    available_days: List[int] = [0, 1, 2, 3, 4]  # Monday to Friday
    consultation_duration: int = 30  # minutes
    max_appointments_per_day: int = 16
    
    # Status
    is_active: bool = True
    is_accepting_new_patients: bool = True
    
    bio: Optional[str] = None
    languages: List[str] = ["English", "Hindi"]
    
    def __str__(self):
        return f"Dr. {self.name} ({self.specialization})"
    
    def is_available_on_day(self, day: int) -> bool:
        return day in self.available_days and self.is_active


class DoctorResponse(BaseModel):
    """API response for doctor operations."""
    success: bool
    message: str
    doctor: Optional[Doctor] = None
    doctors: Optional[List[Doctor]] = None
    error: Optional[str] = None