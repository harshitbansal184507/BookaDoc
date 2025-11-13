from typing import List, Optional, Dict, Any
from datetime import datetime, date, time, timedelta
from bson import ObjectId
import pytz

from app.models.appointment import (
    Appointment,
    AppointmentSlot,
    AppointmentStatus,
    AppointmentResponse
)
from app.config import settings
from app.utils.logger import app_logger as logger
from app.db.mongodb import get_database


class AppointmentService:
    """Service for managing appointments with MongoDB."""
    
    def __init__(self):
        """Initialize appointment service."""
        self.timezone = pytz.timezone(settings.CLINIC_TIMEZONE)
        logger.info("Appointment Service initialized with MongoDB")
    
    def _get_collection(self):
        """Get appointments collection."""
        db = get_database()
        return db.appointments if db is not None else None
    
    async def create_appointment(
        self,
        patient_name: str,
        patient_phone: str,
        appointment_date: date,
        appointment_time: time,
        doctor_id: str,
        doctor_name: str,
        reason: Optional[str] = None,
        patient_email: Optional[str] = None,
        duration_minutes: int = 30
    ) -> AppointmentResponse:
        """Create a new appointment in MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return AppointmentResponse(
                    success=False,
                    message="Database not available",
                    error="MongoDB not connected"
                )
            
            # Check if slot is available
            if not await self._is_slot_available(appointment_date, appointment_time, doctor_id):
                return AppointmentResponse(
                    success=False,
                    message="This time slot is not available",
                    error="Slot already booked"
                )
            
            # Create appointment document
            appointment_doc = {
                "patient_name": patient_name,
                "patient_phone": patient_phone,
                "patient_email": patient_email,
                "appointment_date": datetime.combine(appointment_date, datetime.min.time()),
                "appointment_time": appointment_time.isoformat(),
                "duration_minutes": duration_minutes,
                "doctor_name": doctor_name,
                "doctor_id": doctor_id,
                "reason": reason,
                "status": AppointmentStatus.SCHEDULED.value,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "confirmed_at": None,
                "conversation_id": None,
                "notes": None
            }
            
            # Insert into MongoDB
            result = await collection.insert_one(appointment_doc)
            appointment_doc["_id"] = str(result.inserted_id)
            
            # Convert to Appointment model
            appointment = self._doc_to_model(appointment_doc)
            
            logger.info(f"Appointment created in MongoDB: {appointment.appointment_id}")
            
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
    
    async def get_appointment(self, appointment_id: str) -> Optional[Appointment]:
        """Get appointment by ID from MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return None
            
            doc = await collection.find_one({"_id": ObjectId(appointment_id)})
            
            if doc:
                return self._doc_to_model(doc)
            return None
            
        except Exception as e:
            logger.error(f"Error getting appointment: {e}")
            return None
    
    async def get_all_appointments(self) -> List[Appointment]:
        """Get all appointments from MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return []
            
            cursor = collection.find({})
            
            appointments = []
            async for doc in cursor:
                appointments.append(self._doc_to_model(doc))
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting appointments: {e}")
            return []
    
    async def update_appointment_status(
        self,
        appointment_id: str,
        status: AppointmentStatus
    ) -> AppointmentResponse:
        """Update appointment status in MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return AppointmentResponse(
                    success=False,
                    message="Database not available",
                    error="MongoDB not connected"
                )
            
            update_data = {
                "status": status.value,
                "updated_at": datetime.now()
            }
            
            if status == AppointmentStatus.CONFIRMED:
                update_data["confirmed_at"] = datetime.now()
            
            result = await collection.update_one(
                {"_id": ObjectId(appointment_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                return AppointmentResponse(
                    success=False,
                    message="Appointment not found",
                    error="Invalid appointment ID"
                )
            
            # Get updated appointment
            appointment = await self.get_appointment(appointment_id)
            
            logger.info(f"Appointment {appointment_id} status updated to {status}")
            
            return AppointmentResponse(
                success=True,
                message=f"Appointment status updated to {status}",
                appointment=appointment
            )
            
        except Exception as e:
            logger.error(f"Error updating appointment: {e}")
            return AppointmentResponse(
                success=False,
                message="Failed to update appointment",
                error=str(e)
            )
    
    async def cancel_appointment(self, appointment_id: str) -> AppointmentResponse:
        """Cancel an appointment in MongoDB."""
        return await self.update_appointment_status(
            appointment_id,
            AppointmentStatus.CANCELLED
        )
    
    async def get_available_slots(
        self,
        doctor_id: str,
        doctor_name: str,
        start_date: date,
        num_days: int = 7
    ) -> List[AppointmentSlot]:
        """Get available appointment slots."""
        available_slots = []
        
        for day_offset in range(num_days):
            check_date = start_date + timedelta(days=day_offset)
            day_of_week = check_date.weekday()
            
            # Skip weekends
            if day_of_week >= 5:
                continue
            
            # Generate slots for this day
            current_hour = settings.CLINIC_OPEN_HOUR
            
            while current_hour < settings.CLINIC_CLOSE_HOUR:
                slot_time = time(current_hour, 0)
                
                # Check if slot is available
                if await self._is_slot_available(check_date, slot_time, doctor_id):
                    slot = AppointmentSlot(
                        date=check_date,
                        start_time=slot_time,
                        end_time=time((current_hour + 1) % 24, 0),
                        doctor_name=doctor_name,
                        doctor_id=doctor_id,
                        is_available=True
                    )
                    available_slots.append(slot)
                
                current_hour += 1
        
        logger.info(f"Found {len(available_slots)} available slots for {doctor_name}")
        return available_slots
    
    async def find_slots_by_preference(
        self,
        doctor_id: str,
        doctor_name: str,
        preferred_date: Optional[date] = None,
        preferred_time: Optional[str] = None,
        num_slots: int = 5
    ) -> List[AppointmentSlot]:
        """Find slots matching preferences."""
        start_date = preferred_date or date.today()
        all_slots = await self.get_available_slots(doctor_id, doctor_name, start_date, num_days=14)
        
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
        
        return all_slots[:num_slots]
    
    async def _is_slot_available(
        self,
        appointment_date: date,
        appointment_time: time,
        doctor_id: str
    ) -> bool:
        """Check if a slot is available in MongoDB."""
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("MongoDB not connected")
                return False
            
            # Check for existing appointment
            existing = await collection.find_one({
                "doctor_id": doctor_id,
                "appointment_date": datetime.combine(appointment_date, datetime.min.time()),
                "appointment_time": appointment_time.isoformat(),
                "status": {"$in": [
                    AppointmentStatus.SCHEDULED.value,
                    AppointmentStatus.CONFIRMED.value
                ]}
            })
            
            return existing is None
            
        except Exception as e:
            logger.error(f"Error checking slot availability: {e}")
            return False
    
    def _doc_to_model(self, doc: Dict) -> Appointment:
        """Convert MongoDB document to Appointment model."""
        # Parse date
        appointment_date = doc["appointment_date"]
        if isinstance(appointment_date, datetime):
            appointment_date = appointment_date.date()
        
        # Parse time
        appointment_time_str = doc["appointment_time"]
        if isinstance(appointment_time_str, str):
            appointment_time = time.fromisoformat(appointment_time_str)
        else:
            appointment_time = appointment_time_str
        
        return Appointment(
            appointment_id=str(doc["_id"]),
            patient_name=doc["patient_name"],
            patient_phone=doc["patient_phone"],
            patient_email=doc.get("patient_email"),
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration_minutes=doc.get("duration_minutes", 30),
            doctor_name=doc["doctor_name"],
            doctor_id=doc["doctor_id"],
            reason=doc.get("reason"),
            status=AppointmentStatus(doc["status"]),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            confirmed_at=doc.get("confirmed_at"),
            conversation_id=doc.get("conversation_id"),
            notes=doc.get("notes")
        )


# Create singleton instance
appointment_service = AppointmentService()