from typing import Dict, Any, Optional, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.config import settings
from app.utils.logger import app_logger as logger


class BaseAgent:
    
    def __init__(self, name: str, system_prompt: str):
      
        self.name = name
        self.system_prompt = system_prompt
        self.llm = self._initialize_llm()
        logger.info(f"Agent '{name}' initialized")
    
    def _initialize_llm(self):
        #this is beacuase intiallty we weren't sure of which model we'll use 
        if settings.LLM_PROVIDER == "anthropic":
            return ChatAnthropic(
                model=settings.LLM_MODEL,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                temperature=0.7,
                max_tokens=1024
            )
        else:  # openai
            return ChatOpenAI(
                model=settings.LLM_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=0.7,
                max_tokens=1024
            )
    
    def create_messages(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[BaseMessage]:
     
        messages = [SystemMessage(content=self.system_prompt)]
        
        if context:
            context_str = self._format_context(context)
            if context_str:
                messages.append(SystemMessage(content=f"Context:\n{context_str}"))
        
        messages.append(HumanMessage(content=user_message))
        
        return messages
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary into string."""
        formatted = []
        for key, value in context.items():
            if value:
                formatted.append(f"- {key}: {value}")
        return "\n".join(formatted) if formatted else ""
    
    async def process(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:

        try:
            messages = self.create_messages(user_message, context)
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error in {self.name}: {e}")
            return f"I apologize, but I encountered an error. Please try again."