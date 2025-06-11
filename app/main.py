# app/main.py - Clean and optimized FastAPI application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os

from app.database import engine, Base
from app import auth, folders, quiz

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
    logger.info("🚀 Starting VocabBuilder API...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created/verified")

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["🔐 Authentication & Profile"])
app.include_router(folders.router, prefix="/folders", tags=["📁 Folders & Vocabulary"])
app.include_router(quiz.router, prefix="/quiz", tags=["🧠 Quiz System"])


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