# app/main.py - Clean and optimized FastAPI application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="VocabBuilder API",
    description="🚀 Clean and simple vocabulary learning API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (for avatars)
os.makedirs("app/static/uploads/avatars", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Create database tables on startup
@app.on_event("startup")
async def startup():
    try:
        logger.info("🚀 Starting VocabBuilder API...")
        from app.database import engine, Base
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")


# Basic test endpoints
@app.get("/")
async def root():
    """API status endpoint"""
    return {
        "message": "🚀 VocabBuilder API v2.0 is running!",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "healthy",
        "features": [
            "🔐 Authentication with email verification",
            "👤 User profiles with avatars",
            "📁 Folder management with sharing",
            "📚 Vocabulary management",
            "🧠 Interactive quiz system",
            "📊 Statistics and history"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "vocabbuilder-api",
        "version": "2.0.0",
        "database": "connected"
    }


@app.get("/test")
async def test_endpoint():
    """Test endpoint to check if API is working"""
    try:
        from app.config import settings
        return {
            "status": "working",
            "database_url": settings.database_url,
            "email_configured": settings.is_email_configured(),
            "debug": settings.debug
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/test-db")
async def test_database():
    """Test database connection"""
    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()

        return {
            "status": "database_working",
            "result": row[0] if row else None
        }
    except Exception as e:
        return {
            "status": "database_error",
            "error": str(e)
        }


# Include routers (with error handling)
try:
    from app import auth, folders, quiz

    app.include_router(auth.router, prefix="/auth", tags=["🔐 Authentication & Profile"])
    app.include_router(folders.router, prefix="/folders", tags=["📁 Folders & Vocabulary"])
    app.include_router(quiz.router, prefix="/quiz", tags=["🧠 Quiz System"])
    logger.info("✅ All routers included successfully")
except Exception as e:
    logger.error(f"❌ Error including routers: {str(e)}")


# Error handler for debugging
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"❌ Global error: {str(exc)}")
    return {
        "error": "Internal server error",
        "detail": str(exc) if app.debug else "Contact support"
    }