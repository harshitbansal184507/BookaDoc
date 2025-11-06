from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.config import settings
from app.utils.logger import app_logger as logger
import json


class LLMService:
    """Service for interacting with OpenAI LLMs."""

    def __init__(self):
        """Initialize LLM service with OpenAI."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL
        logger.info(f"LLM Service initialized with OpenAI model: {self.model}")

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str:
        """
        Generate a response using OpenAI.
        """
        try:
            formatted_messages = []
            if system_prompt:
                formatted_messages.append({"role": "system", "content": system_prompt})
            formatted_messages.extend(messages)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content
            logger.debug(f"OpenAI response: {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def extract_information(
        self,
        text: str,
        extraction_prompt: str
    ) -> Dict[str, Any]:
        """
        Extract structured information from text using LLM.
        """
        messages = [
            {
                "role": "user",
                "content": f"{extraction_prompt}\n\nText: {text}\n\nExtract the information in JSON format."
            }
        ]

        response = await self.generate_response(
            messages=messages,
            temperature=0.3,
            max_tokens=512
        )

        # Try to parse JSON from response
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM response: {response}")
            return {}

    async def classify_intent(
        self,
        user_message: str,
        intents: List[str]
    ) -> str:
        """
        Classify user intent from a list of possible intents.
        """
        prompt = f"""Classify the user's intent from the following options:
{', '.join(intents)}

User message: {user_message}

Respond with only the intent name, nothing else."""

        messages = [{"role": "user", "content": prompt}]
        response = await self.generate_response(
            messages=messages,
            temperature=0.1,
            max_tokens=50
        )

        return response.strip().lower()


# Create singleton instance
llm_service = LLMService()
