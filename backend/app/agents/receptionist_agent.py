from typing import Dict, Any, Optional
import json
from app.agents.base_agent import BaseAgent
from app.utils.logger import app_logger as logger


class ReceptionistAgent(BaseAgent):
    def __init__(self):
        system_prompt = """You are a friendly and professional medical receptionist at BookaDoc clinic.

Your responsibilities:
1. Greet patients warmly and make them feel comfortable
2. Gather essential information:(ask for all at once)
   - Patient's full name
   - Contact phone number
   - Reason for visit (brief description)
   - Any doctor preference (if not provided fill with null)
   - Preferred date/time (time morning evening afgternoon )



Format your final response with: "READY_TO_SCHEDULE" when all required info is collected.
 READY_TO_SCHEDULE"
"""
        super().__init__(name="Receptionist", system_prompt=system_prompt)
    
    async def extract_information(
        self,
        conversation_history: list,
        latest_message: str
    ) -> Dict[str, Any]:
        """
        Extract structured information from conversation.
        
        Args:
            conversation_history: Previous messages
            latest_message: Latest user message
            
        Returns:
            Extracted information dictionary
        """
        extraction_prompt = f"""Extract the following information from the conversation:
- patient_name: Full name of the patient
- patient_phone: Phone number (10 digits)
- reason: Reason for visit
- doctor_preference: Any doctor name mentioned (or null)
- preferred_date: Any date mentioned (or null)
- preferred_time: Time preference like "morning", "afternoon", "evening" (or null)

Conversation:
{self._format_conversation(conversation_history)}

Latest message: {latest_message}

Return ONLY a valid JSON object with these fields. Use null for missing information.
Example: {{"patient_name": "John Doe", "patient_phone": "9876543210", "reason": "Cough", "doctor_preference": null, "preferred_date": null, "preferred_time": null}}
"""
        
        try:
            messages = [{"role": "user", "content": extraction_prompt}]
            response = await self.llm.ainvoke([
                {"role": "user", "content": extraction_prompt}
            ])
            
            # Parse JSON response
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            extracted = json.loads(content)
            logger.info(f"Extracted info: {extracted}")
            return extracted
            
        except Exception as e:
            logger.error(f"Error extracting information: {e}")
            return {}
    
    def _format_conversation(self, conversation_history: list) -> str:
        """Format conversation history for extraction."""
        formatted = []
        for msg in conversation_history:
            role = "Patient" if msg.get("role") == "user" else "Receptionist"
            formatted.append(f"{role}: {msg.get('content', '')}")
        return "\n".join(formatted)
    
    def has_required_info(self, extracted_info: Dict[str, Any]) -> bool:
        required_fields = ["patient_name", "patient_phone", "reason"]
    
    # Check only required ones for completeness
        for field in required_fields:
            value = extracted_info.get(field)
            if not value or value in ["null", None, ""]:
                return False
        return True
