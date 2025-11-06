import sys
from loguru import logger
from app.config import settings


def setup_logger():
    """Configure application logger."""
    
    # Remove default logger
    logger.remove()
    
    # Console logging with color
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
    )
    
    # File logging
    logger.add(
        settings.LOG_FILE,
        rotation="500 MB",
        retention="10 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
    )
    
    logger.info(f"Logger initialized - Level: {settings.LOG_LEVEL}")
    return logger


# Initialize logger
app_logger = setup_logger()