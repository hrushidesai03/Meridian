import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database.db import connect_db, disconnect_db
from routers import sessions, commitments, decisions, alerts, search, reports
from routers import webhooks as webhook_router
from routers import comprehensive_dashboard
from webhooks import videodb as videodb_webhooks
from scheduler import start_scheduler, stop_scheduler
from sandbox_manager import get_sandbox_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Starting Meridian API server...")
    try:
        await connect_db()
        logger.info("Database connection established")
        
        # Initialize sandbox manager for AI workloads
        try:
            sandbox_manager = get_sandbox_manager()
            logger.info("Sandbox manager initialized for hackathon compute")
        except Exception as e:
            logger.warning(f"Sandbox manager initialization failed (optional): {e}")
        
        await start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Meridian API server...")
    await stop_scheduler()
    await disconnect_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Commitment tracking with drift detection and accountability receipts",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routers
app.include_router(webhook_router.router)
app.include_router(videodb_webhooks.router)
app.include_router(sessions.router)
app.include_router(commitments.router)
app.include_router(decisions.router)
app.include_router(alerts.router)
app.include_router(search.router)
app.include_router(reports.router)
app.include_router(comprehensive_dashboard.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "message": "Meridian API - Commitment tracking with drift detection",
        "docs": "/docs"
    }


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    logger.error(f"ValueError: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
