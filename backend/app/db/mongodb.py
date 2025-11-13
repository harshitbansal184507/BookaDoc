from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.config import settings
from app.utils.logger import app_logger as logger

# Global MongoDB client
mongodb_client: AsyncIOMotorClient = None
database = None


async def connect_to_mongo():
    """Connect to MongoDB."""
    global mongodb_client, database
    
    try:
        mongodb_client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        
        # Test connection
        await mongodb_client.admin.command('ping')
        
        database = mongodb_client[settings.MONGODB_DB_NAME]
        
        logger.info(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")
        
        # Create indexes
        await create_indexes()
        
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection."""
    global mongodb_client
    
    if mongodb_client is not None:  # FIXED: Compare with None
        mongodb_client.close()
        logger.info("Closed MongoDB connection")


async def create_indexes():
    """Create database indexes for better performance."""
    global database
    
    if database is None:  # FIXED: Compare with None
        return
    
    try:
        # Appointments indexes
        await database.appointments.create_index("patient_phone")
        await database.appointments.create_index("appointment_date")
        await database.appointments.create_index("doctor_id")
        await database.appointments.create_index([("doctor_id", 1), ("appointment_date", 1)])
        
        # Doctors indexes
        await database.doctors.create_index("specialization")
        await database.doctors.create_index("is_active")
        await database.doctors.create_index("doctor_id", unique=True)  # ADDED: Unique constraint
        
        # Conversations indexes
        await database.conversations.create_index("created_at")
        
        logger.info("MongoDB indexes created")
    except Exception as e:
        logger.warning(f"Error creating indexes: {e}")


def get_database():
    """Get database instance."""
    return database