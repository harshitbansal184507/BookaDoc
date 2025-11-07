from typing import List, Optional, Dict, Any
from datetime import datetime, date, time, timedelta
import pytz

from app.models.appointment import (
    Appointment,
    AppointmentSlot,
    AppointmentRequest,
    AppointmentStatus,
    AppointmentResponse
)
from app.models.doctor import Doctor
from app.config import settings
from app.utils.logger import app_logger as logger


class AppointmentService:
    """Service for managing appointments."""
    
    def __init__(self):
        """Initialize appointment service with in-memory storage."""
        # In-memory storage (replace with database later)
        self.appointments: Dict[str, Appointment] = {}
        self.booked_slots: List[Dict[str, Any]] = []
        
        # Timezone
        self.timezone = pytz.timezone(settings.CLINIC_TIMEZONE)
        
        logger.info("Appointment Service initialized")
    
    def create_appointment(
        self,
        patient_name: str,
        patient_phone: str,
        appointment_date: date,
        appointment_time: time,
        doctor: Doctor,  # Changed from doctor_name to doctor object
        reason: Optional[str] = None,
        patient_email: Optional[str] = None
    ) -> AppointmentResponse:
        """
        Create a new appointment.
        
        Args:
            patient_name: Patient's full name
            patient_phone: Patient's phone number
            appointment_date: Date of appointment
            appointment_time: Time of appointment
            doctor: Doctor object
            reason: Reason for visit
            patient_email: Patient's email (optional)
            
        Returns:
            AppointmentResponse with success status and appointment details
        """
        try:
            # Check if doctor is available on this day
            day_of_week = appointment_date.weekday()
            if not doctor.is_available_on_day(day_of_week):
                return AppointmentResponse(
                    success=False,
                    message=f"Dr. {doctor.name} is not available on this day",
                    error="Doctor not available"
                )
            
            # Check if slot is available
            if not self._is_slot_available(appointment_date, appointment_time, doctor.doctor_id):
                return AppointmentResponse(
                    success=False,
                    message="This time slot is not available",
                    error="Slot already booked"
                )
            
            # Create appointment
            appointment = Appointment(
                patient_name=patient_name,
                patient_phone=patient_phone,
                patient_email=patient_email,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                doctor_name=f"Dr. {doctor.name}",
                doctor_id=doctor.doctor_id,  # Store doctor ID
                reason=reason,
                status=AppointmentStatus.SCHEDULED,
                duration_minutes=doctor.consultation_duration
            )
            
            # Store appointment
            self.appointments[appointment.appointment_id] = appointment
            
            # Mark slot as booked
            self._mark_slot_booked(appointment_date, appointment_time, doctor.doctor_id)
            
            logger.info(f"Appointment created: {appointment.appointment_id} with Dr. {doctor.name}")
            
            return AppointmentResponse(
                success=True,
                message="Appointment created successfully",
                appointment=appointment
            )
            
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return AppointmentResponse(
                success=False,
                message="Failed to create appointment",
                error=str(e)
            )
    
    def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Get appointment by ID."""
        return self.appointments.get(appointment_id)
    
    def get_all_appointments(self) -> List[Appointment]:
        """Get all appointments."""
        return list(self.appointments.values())
    
    def get_appointments_by_doctor(self, doctor_id: str) -> List[Appointment]:
        """Get all appointments for a specific doctor."""
        return [
            apt for apt in self.appointments.values()
            if apt.doctor_id == doctor_id
        ]
    
    def update_appointment_status(
        self,
        appointment_id: str,
        status: AppointmentStatus
    ) -> AppointmentResponse:
        """Update appointment status."""
        appointment = self.appointments.get(appointment_id)
        
        if not appointment:
            return AppointmentResponse(
                success=False,
                message="Appointment not found",
                error="Invalid appointment ID"
            )
        
        appointment.status = status
        appointment.updated_at = datetime.now()
        
        if status == AppointmentStatus.CONFIRMED:
            appointment.confirmed_at = datetime.now()
        
        logger.info(f"Appointment {appointment_id} status updated to {status}")
        
        return AppointmentResponse(
            success=True,
            message=f"Appointment status updated to {status}",
            appointment=appointment
        )
    
    def cancel_appointment(self, appointment_id: str) -> AppointmentResponse:
        """Cancel an appointment."""
        appointment = self.appointments.get(appointment_id)
        
        if not appointment:
            return AppointmentResponse(
                success=False,
                message="Appointment not found",
                error="Invalid appointment ID"
            )
        
        # Free up the slot
        self._free_slot(
            appointment.appointment_date,
            appointment.appointment_time,
            appointment.doctor_id
        )
        
        # Update status
        appointment.status = AppointmentStatus.CANCELLED
        appointment.updated_at = datetime.now()
        
        logger.info(f"Appointment {appointment_id} cancelled")
        
        return AppointmentResponse(
            success=True,
            message="Appointment cancelled successfully",
            appointment=appointment
        )
    
    def get_available_slots(
        self,
        doctor: Doctor,
        start_date: date,
        num_days: int = 7
    ) -> List[AppointmentSlot]:
        """
        Get available appointment slots for a specific doctor.
        
        Args:
            doctor: Doctor object
            start_date: Starting date to check
            num_days: Number of days to look ahead
            
        Returns:
            List of available slots
        """
        available_slots = []
        
        for day_offset in range(num_days):
            check_date = start_date + timedelta(days=day_offset)
            day_of_week = check_date.weekday()
            
            # Check if doctor is available on this day
            if not doctor.is_available_on_day(day_of_week):
                continue
            
            # Generate slots for this day
            current_hour = settings.CLINIC_OPEN_HOUR
            
            while current_hour < settings.CLINIC_CLOSE_HOUR:
                slot_time = time(current_hour, 0)
                
                # Check if slot is available
                if self._is_slot_available(check_date, slot_time, doctor.doctor_id):
                    slot = AppointmentSlot(
                        date=check_date,
                        start_time=slot_time,
                        end_time=time(
                            (current_hour + 1) % 24, 0
                        ),
                        doctor_name=f"Dr. {doctor.name}",
                        doctor_id=doctor.doctor_id,
                        is_available=True
                    )
                    available_slots.append(slot)
                
                current_hour += 1
        
        logger.info(f"Found {len(available_slots)} available slots for Dr. {doctor.name}")
        return available_slots
    
    def find_slots_by_preference(
        self,
        doctor: Doctor,
        preferred_date: Optional[date] = None,
        preferred_time: Optional[str] = None,
        num_slots: int = 3
    ) -> List[AppointmentSlot]:
        """
        Find slots matching user preferences for a specific doctor.
        
        Args:
            doctor: Doctor object
            preferred_date: Preferred date (or start from today)
            preferred_time: Preferred time of day ("morning", "afternoon", "evening")
            num_slots: Number of slots to return
            
        Returns:
            List of matching slots
        """
        start_date = preferred_date or date.today()
        all_slots = self.get_available_slots(doctor, start_date, num_days=14)
        
        # Filter by time preference
        if preferred_time:
            filtered_slots = []
            for slot in all_slots:
                hour = slot.start_time.hour
                
                if preferred_time.lower() == "morning" and 9 <= hour < 12:
                    filtered_slots.append(slot)
                elif preferred_time.lower() == "afternoon" and 12 <= hour < 17:
                    filtered_slots.append(slot)
                elif preferred_time.lower() == "evening" and 17 <= hour < 20:
                    filtered_slots.append(slot)
            
            all_slots = filtered_slots
        
        # Return requested number of slots
        return all_slots[:num_slots]
    
    def _is_slot_available(
        self,
        appointment_date: date,
        appointment_time: time,
        doctor_id: str
    ) -> bool:
        """Check if a specific slot is available for a doctor."""
        for booked in self.booked_slots:
            if (booked["date"] == appointment_date and 
                booked["time"] == appointment_time and
                booked["doctor_id"] == doctor_id):
                return False
        return True
    
    def _mark_slot_booked(
        self,
        appointment_date: date,
        appointment_time: time,
        doctor_id: str
    ):
        """Mark a slot as booked for a specific doctor."""
        self.booked_slots.append({
            "date": appointment_date,
            "time": appointment_time,
            "doctor_id": doctor_id
        })
    
    def _free_slot(
        self,
        appointment_date: date,
        appointment_time: time,
        doctor_id: str
    ):
        """Free up a booked slot for a specific doctor."""
        self.booked_slots = [
            slot for slot in self.booked_slots
            if not (slot["date"] == appointment_date and 
                   slot["time"] == appointment_time and
                   slot["doctor_id"] == doctor_id)
        ]


# Create singleton instance
appointment_service = AppointmentService()