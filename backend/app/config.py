from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os


class Settings(BaseSettings):
    """Application configuration settings."""
    
    # Application
    APP_NAME: str = "BookaDoc"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    #MONGODB SETTINGS

    MONGODB_URL : str = os.getenv("MONGODB_URL", "mongodb+srv://<your-fallback-url>")
    MONGODB_DB_NAME: str = "bookadoc_db"
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # LLM Configuration
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str
    LLM_PROVIDER: str = "openai"  # anthropic or openai
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Speech-to-Text (Optional)
    DEEPGRAM_API_KEY: str = ""
    
    # Appointment Settings
    DEFAULT_APPOINTMENT_DURATION: int = 30  # minutes
    CLINIC_OPEN_HOUR: int = 9
    CLINIC_CLOSE_HOUR: int = 17
    CLINIC_TIMEZONE: str = "Asia/Kolkata"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    def validate_llm_config(self) -> bool:
        """Validate LLM configuration."""
        if self.LLM_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        return True


settings = Settings()

os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)