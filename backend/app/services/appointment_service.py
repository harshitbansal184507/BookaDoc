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
from app.config import settings
from app.utils.logger import app_logger as logger


class AppointmentService:
    
    def __init__(self):
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
        reason: Optional[str] = None,
        patient_email: Optional[str] = None,
        doctor_name: str = "Dr. Smith"
    ) -> AppointmentResponse:
      
        try:
            if not self._is_slot_available(appointment_date, appointment_time):
                return AppointmentResponse(
                    success=False,
                    message="This time slot is not available",
                    error="Slot already booked"
                )
            
            appointment = Appointment(
                patient_name=patient_name,
                patient_phone=patient_phone,
                patient_email=patient_email,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                doctor_name=doctor_name,
                reason=reason,
                status=AppointmentStatus.SCHEDULED,
                duration_minutes=settings.DEFAULT_APPOINTMENT_DURATION
            )
            
            self.appointments[appointment.appointment_id] = appointment
            
            self._mark_slot_booked(appointment_date, appointment_time)
            
            logger.info(f"Appointment created: {appointment.appointment_id}")
            
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
        self._free_slot(appointment.appointment_date, appointment.appointment_time)
        
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
        start_date: date,
        num_days: int = 7,
        doctor_name: Optional[str] = None
    ) -> List[AppointmentSlot]:
        """
        Get available appointment slots.
        
        Args:
            start_date: Starting date to check
            num_days: Number of days to look ahead
            doctor_name: Filter by doctor (optional)
            
        Returns:
            List of available slots
        """
        available_slots = []
        
        for day_offset in range(num_days):
            check_date = start_date + timedelta(days=day_offset)
            
            # Skip weekends (Saturday=5, Sunday=6)
            if check_date.weekday() >= 5:
                continue
            
            # Generate slots for this day
            current_hour = settings.CLINIC_OPEN_HOUR
            
            while current_hour < settings.CLINIC_CLOSE_HOUR:
                slot_time = time(current_hour, 0)
                
                # Check if slot is available
                if self._is_slot_available(check_date, slot_time):
                    slot = AppointmentSlot(
                        date=check_date,
                        start_time=slot_time,
                        end_time=time(
                            current_hour,
                            settings.DEFAULT_APPOINTMENT_DURATION
                        ) if current_hour == settings.CLINIC_CLOSE_HOUR - 1 
                        else time(current_hour + 1, 0),
                        doctor_name=doctor_name or "Dr. Smith",
                        is_available=True
                    )
                    available_slots.append(slot)
                
                current_hour += 1
        
        logger.info(f"Found {len(available_slots)} available slots")
        return available_slots
    
    def find_slots_by_preference(
        self,
        preferred_date: Optional[date] = None,
        preferred_time: Optional[str] = None,
        num_slots: int = 3
    ) -> List[AppointmentSlot]:
        """
        Find slots matching user preferences.
        
        Args:
            preferred_date: Preferred date (or start from today)
            preferred_time: Preferred time of day ("morning", "afternoon", "evening")
            num_slots: Number of slots to return
            
        Returns:
            List of matching slots
        """
        start_date = preferred_date or date.today()
        all_slots = self.get_available_slots(start_date, num_days=14)
        
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
    
    def _is_slot_available(self, appointment_date: date, appointment_time: time) -> bool:
        """Check if a specific slot is available."""
        for booked in self.booked_slots:
            if (booked["date"] == appointment_date and 
                booked["time"] == appointment_time):
                return False
        return True
    
    def _mark_slot_booked(self, appointment_date: date, appointment_time: time):
        """Mark a slot as booked."""
        self.booked_slots.append({
            "date": appointment_date,
            "time": appointment_time
        })
    
    def _free_slot(self, appointment_date: date, appointment_time: time):
        """Free up a booked slot."""
        self.booked_slots = [
            slot for slot in self.booked_slots
            if not (slot["date"] == appointment_date and slot["time"] == appointment_time)
        ]


# Create singleton instance
appointment_service = AppointmentService()