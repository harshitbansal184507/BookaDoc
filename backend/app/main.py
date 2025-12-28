from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.utils.logger import app_logger as logger
from app.api import api_router, ws_router
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.services.doctor_service import doctor_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    try:
        logger.info("Connecting to MongoDB Atlas...")
        await connect_to_mongo()
        logger.info("✅ MongoDB connected successfully")
        
        # Initialize doctors
        logger.info("Initializing doctors...")
        success = await doctor_service.initialize_doctors()
        
        if success:
            logger.info("✅ Doctors initialized successfully")
            
            # Verify doctors
            doctors = await doctor_service.get_all_doctors()
            logger.info(f"✅ Found {len(doctors)} doctors in database")
        else:
            logger.warning("⚠️  Failed to initialize doctors")
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        logger.error("Full error:", exc_info=True)
        logger.warning("⚠️  Running without database - data will not persist")
    
    # Validate LLM configuration
    try:
        settings.validate_llm_config()
        logger.info(f"✅ LLM Provider: {settings.LLM_PROVIDER}")
        logger.info(f"✅ LLM Model: {settings.LLM_MODEL}")
    except ValueError as e:
        logger.error(f"❌ LLM Configuration Error: {e}")
        raise
    
    logger.info("="*70)
    logger.info("🚀 Application started successfully!")
    logger.info("="*70)
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
    await close_mongo_connection()


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.db.mongodb import get_database
    
    db = get_database()
    db_status = "disconnected"
    doctors_count = 0
    appointments_count = 0
    
    if db:
        db_status = "connected"
        try:
            doctors_count = await db.doctors.count_documents({})
            appointments_count = await db.appointments.count_documents({})
        except:
            pass
    
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
        "doctors_count": doctors_count,
        "appointments_count": appointments_count,
        "llm_provider": settings.LLM_PROVIDER
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )