from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.database import engine, Base
from app.api import auth, users
from app.services.email_service import email_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle
    - Initialize services on startup
    - Clean up on shutdown
    """
    # Startup
    logger.info("Starting VocabBuilder Auth API...")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    # Test email service connection
    email_healthy = await email_service.health_check()
    if email_healthy:
        logger.info("Email service initialized successfully")
    else:
        logger.warning("Email service health check failed - emails may not send")

    yield

    # Shutdown
    logger.info("Shutting down VocabBuilder Auth API...")
    await email_service.close()
    logger.info("Email service connections closed")


# Create FastAPI app with lifecycle management
app = FastAPI(
    title="VocabBuilder Auth API",
    description="Crystal clear authentication API for VocabBuilder mobile app",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/auth", tags=["Users"])


@app.get("/")
async def root():
    return {
        "message": "🚀 VocabBuilder Auth API is running!",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    email_healthy = await email_service.health_check()

    return {
        "status": "healthy" if email_healthy else "degraded",
        "service": "vocabbuilder-auth",
        "components": {
            "database": "healthy",  # Add actual DB check if needed
            "email": "healthy" if email_healthy else "unhealthy"
        }
    }