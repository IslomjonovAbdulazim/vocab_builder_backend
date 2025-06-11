# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.database import engine, Base
from app.api import auth, users, folders, quiz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="VocabBuilder Auth API",
    description="Crystal clear authentication API for VocabBuilder mobile app",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables on startup
@app.on_event("startup")
async def startup():
    logger.info("Starting VocabBuilder Auth API...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

# Include API routes
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/auth", tags=["Users"])

# NEW MVP ROUTES
app.include_router(folders.router, prefix="/folders", tags=["Folders"])
app.include_router(quiz.router, prefix="/quiz", tags=["Quiz"])


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
    """Simple health check"""
    return {
        "status": "healthy",
        "service": "vocabbuilder-auth",
        "database": "healthy"
    }