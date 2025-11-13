from typing import Dict, Any, Optional
from datetime import datetime
from app.agents.base_agent import BaseAgent
from app.services.appointment_service import appointment_service
from app.services.doctor_service import doctor_service
from app.models.appointment import AppointmentStatus
from app.utils.logger import app_logger as logger


class ConfirmationAgent(BaseAgent):
    """Agent responsible for confirming and finalizing appointments."""
    
    def __init__(self):
        system_prompt = """You are a professional medical appointment confirmation specialist at BookaDoc clinic.

Your responsibilities:
1. Confirm appointment details with the patient
2. Create the appointment in the system
3. Provide confirmation details clearly
4. Answer any final questions

Guidelines:
- Present all details for confirmation before finalizing
- Be clear and precise about date, time, and doctor
- Provide a confirmation number/ID
- Give any necessary instructions (arrive early, bring documents, etc.)
- End on a positive, reassuring note

Confirmation format:
"Let me confirm your appointment details:
- Patient: [Name]
- Doctor: [Doctor Name & Specialization]
- Date & Time: [Day, Date at Time]
- Reason: [Reason]

Is this correct? Please reply 'confirm' to finalize your appointment."

After confirmation:
"✅ Your appointment is confirmed!

Appointment ID: [ID]
Patient: [Name]
Doctor: [Doctor Name]
Date: [Date] at [Time]

Please arrive 10 minutes early. If you need to reschedule, please call us at least 24 hours in advance.

Is there anything else I can help you with?"
"""
        super().__init__(name="Confirmation", system_prompt=system_prompt)
    
    async def create_confirmation_message(
        self,
        patient_info: Dict[str, Any],
        selected_slot: Dict[str, Any]
    ) -> str:
        """
        Create confirmation request message.
        
        Args:
            patient_info: Patient information
            selected_slot: Selected appointment slot
            
        Returns:
            Confirmation message
        """
        date_obj = datetime.fromisoformat(selected_slot["date"])
        time_obj = datetime.fromisoformat(selected_slot["time"]).time()
        
        formatted_date = date_obj.strftime("%A, %B %d, %Y")
        formatted_time = time_obj.strftime("%I:%M %p")
        
        message = f"""Let me confirm your appointment details:

👤 **Patient:** {patient_info.get('patient_name')}
📞 **Phone:** {patient_info.get('patient_phone')}
👨‍⚕️ **Doctor:** {selected_slot['doctor_name']} ({selected_slot['doctor_specialization']})
📅 **Date & Time:** {formatted_date} at {formatted_time}
📝 **Reason:** {patient_info.get('reason')}

Is this correct? Please reply '**confirm**' to finalize your appointment, or let me know if you'd like to make any changes."""
        
        return message
    
    async def finalize_appointment(
        self,
        patient_info: Dict[str, Any],
        selected_slot: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create the appointment in the system.
        
        Args:
            patient_info: Patient information
            selected_slot: Selected slot details
            
        Returns:
            Appointment details or None if failed
        """
        try:
            # Get doctor
            doctor = await doctor_service.get_doctor_by_id(selected_slot['doctor_id'])
            
            if not doctor:
                logger.error(f"Doctor not found: {selected_slot['doctor_id']}")
                return None
            
            appointment_date = datetime.fromisoformat(selected_slot["date"]).date()
            appointment_time = datetime.fromisoformat(selected_slot["time"]).time()
            
            # Create appointment
            result = await appointment_service.create_appointment(
                patient_name=patient_info['patient_name'],
                patient_phone=patient_info['patient_phone'],
                patient_email=patient_info.get('patient_email'),
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                doctor_id=doctor.doctor_id, 
                doctor_name=f"Dr. {doctor.name}",
                reason=patient_info['reason']
            )
            
            if result.success:
                # Update status to confirmed
                appointment_service.update_appointment_status(
                    result.appointment.appointment_id,
                    AppointmentStatus.CONFIRMED
                )
                
                logger.info(f"Appointment confirmed: {result.appointment.appointment_id}")
                
                return {
                    "appointment_id": result.appointment.appointment_id,
                    "appointment": result.appointment
                }
            else:
                logger.error(f"Failed to create appointment: {result.error}")
                return None
                
        except Exception as e:
            logger.error(f"Error finalizing appointment: {e}")
            return None
    
    async def create_success_message(
        self,
        appointment_details: Dict[str, Any]
    ) -> str:
        """
        Create success confirmation message.
        
        Args:
            appointment_details: Appointment details
            
        Returns:
            Success message
        """
        appointment = appointment_details['appointment']
        
        formatted_date = appointment.appointment_date.strftime("%A, %B %d, %Y")
        formatted_time = appointment.appointment_time.strftime("%I:%M %p")
        
        message = f"""✅ **Your appointment is confirmed!**

🆔 **Appointment ID:** {appointment.appointment_id}
👤 **Patient:** {appointment.patient_name}
👨‍⚕️ **Doctor:** {appointment.doctor_name}
📅 **Date:** {formatted_date}
⏰ **Time:** {formatted_time}
📝 **Reason:** {appointment.reason}

**Important reminders:**
- Please arrive 10-15 minutes early
- Bring a valid ID and insurance card (if applicable)
- If you need to reschedule, please call us at least 24 hours in advance

We look forward to seeing you! Is there anything else I can help you with?"""
        
        return message