from typing import Dict, Any, List, Optional
from datetime import date, datetime
from app.agents.base_agent import BaseAgent
from app.services.doctor_service import doctor_service
from app.services.appointment_service import appointment_service
from app.models.doctor import Specialization
from app.utils.logger import app_logger as logger


class SchedulerAgent(BaseAgent):
    """Agent responsible for finding and proposing appointment slots."""
    
    def __init__(self):
        system_prompt = """You are a helpful medical appointment scheduler at BookaDoc clinic.

Your responsibilities:
1. Find available doctors based on patient preferences
2. Present available appointment slots clearly
3. Help patients choose a suitable time
4. Answer questions about doctors and availability

Guidelines:
- Present options in a clear, numbered format
- Include doctor names and specializations
- Show dates and times in a user-friendly format
- Limit to 3-5 options at a time
- Be flexible and offer alternatives if first choice isn't available
- Use natural, conversational language

When presenting slots, format like:
"I found the following available appointments:

1. Dr. Rajesh Kumar (General Physician) - Tomorrow at 10:00 AM
2. Dr. Priya Sharma (Cardiologist) - Tomorrow at 2:00 PM
3. Dr. Neha Gupta (Pediatrician) - Day after tomorrow at 9:00 AM

Which option works best for you? Or would you like to see more times?"
"""
        super().__init__(name="Scheduler", system_prompt=system_prompt)
    
    async def find_suitable_doctor(
        self,
        patient_info: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Find a suitable doctor based on patient preferences.
        
        Args:
            patient_info: Patient information including preferences
            
        Returns:
            Doctor object or None
        """
        doctor_preference = patient_info.get("doctor_preference")
        reason = patient_info.get("reason", "").lower()
        
        if doctor_preference:
            doctor = await doctor_service.get_doctor_by_name(doctor_preference)
            if doctor:
                logger.info(f"Found preferred doctor: {doctor.name}")
                return doctor
        
        specialization = self._infer_specialization(reason)
        
        if specialization:
            doctors = await doctor_service.get_doctors_by_specialization(specialization)
            if doctors:
                logger.info(f"Found {len(doctors)} doctors for {specialization}")
                return doctors[0]  
        
        doctors = await doctor_service.get_doctors_by_specialization(
            Specialization.GENERAL_PHYSICIAN
        )
        if doctors:
            return doctors[0]
        
        all_doctors = await doctor_service.get_all_doctors()
        return all_doctors[0] if all_doctors else None
    
    def _infer_specialization(self, reason: str) -> Optional[Specialization]:
        """Infer medical specialization from reason for visit."""
        reason_lower = reason.lower()
        
        specialization_keywords = {
            Specialization.CARDIOLOGIST: ["heart", "chest pain", "cardiac", "blood pressure", "cholesterol"],
            Specialization.DERMATOLOGIST: ["skin", "rash", "acne", "eczema", "mole", "hair"],
            Specialization.PEDIATRICIAN: ["child", "baby", "infant", "kid", "pediatric"],
            Specialization.ORTHOPEDIC: ["bone", "joint", "fracture", "back pain", "knee", "arthritis"],
            Specialization.GYNECOLOGIST: ["pregnancy", "gynec", "menstrual", "women", "obstetric"],
            Specialization.ENT_SPECIALIST: ["ear", "nose", "throat", "ent", "sinus", "hearing"],
            Specialization.OPHTHALMOLOGIST: ["eye", "vision", "glasses", "cataract"],
            Specialization.PSYCHIATRIST: ["mental", "depression", "anxiety", "stress", "psychiatric"],
            Specialization.DENTIST: ["tooth", "teeth", "dental", "gum", "cavity"]
        }
        
        for specialization, keywords in specialization_keywords.items():
            if any(keyword in reason_lower for keyword in keywords):
                logger.info(f"Inferred specialization: {specialization} from reason: {reason}")
                return specialization
        
        return None
    
    async def get_available_slots(
    self,
    patient_info: Dict[str, Any],
    num_slots: int = 5
) -> List[Dict[str, Any]]:
        """Get available appointment slots."""
        doctor = await self.find_suitable_doctor(patient_info)
    
        if not doctor:
            logger.error("No doctors available")
            return []
    
    # Parse preferred date
        preferred_date = patient_info.get("preferred_date")
        start_date = date.today()
    
        if preferred_date:
            try:
                if isinstance(preferred_date, str):
                    start_date = datetime.strptime(preferred_date, "%Y-%m-%d").date()
                elif isinstance(preferred_date, date):
                    start_date = preferred_date
            except:
                logger.warning(f"Could not parse date: {preferred_date}")
    
    # Get slots - SIMPLIFIED
        preferred_time = patient_info.get("preferred_time")
    
        slots = await appointment_service.find_slots_by_preference(
            doctor_id=doctor.doctor_id,  # Pass ID
            doctor_name=f"Dr. {doctor.name}",  # Pass name
            preferred_date=start_date,
            preferred_time=preferred_time,
            num_slots=num_slots
             )
    
    # Format slots
        formatted_slots = []
        for slot in slots:
            formatted_slots.append({
            "slot_id": slot.slot_id,
            "doctor_name": slot.doctor_name,
            "doctor_id": slot.doctor_id,
            "date": slot.date.isoformat(),
            "time": datetime.combine(slot.date, slot.start_time).isoformat(),
            "formatted": str(slot),
            "doctor_specialization": doctor.specialization.value
        })
    
        logger.info(f"Found {len(formatted_slots)} slots for {doctor.name}")
        return formatted_slots
    
    async def format_slots_message(
        self,
        slots: List[Dict[str, Any]]
    ) -> str:
        """
        Format slots into a user-friendly message.
        
        Args:
            slots: List of slot dictionaries
            
        Returns:
            Formatted message
        """
        if not slots:
            return "I apologize, but I couldn't find any available slots at the moment. Would you like to try different dates or times?"
        
        message = "I found the following available appointments:\n\n"
        
        for i, slot in enumerate(slots, 1):
            date_obj = datetime.fromisoformat(slot["date"])
            time_obj = datetime.fromisoformat(slot["time"]).time()
            
            formatted_date = date_obj.strftime("%A, %B %d")
            formatted_time = time_obj.strftime("%I:%M %p")
            
            message += f"{i}. **{slot['doctor_name']}** ({slot['doctor_specialization']})\n"
            message += f"   📅 {formatted_date} at {formatted_time}\n\n"
        
        message += "Which appointment would you like to book? You can reply with the number (1, 2, 3, etc.)"
        
        return message