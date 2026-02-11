from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import time
from datetime import datetime
import logging
import sys
from pathlib import Path

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Import Database first to apply base schema
from app.db.database import Database

# Determine database path
from app.core.config import settings
db_path = settings.database_path or "gameapy.db"

# Initialize db as None - will be set during startup event
db = None

app = FastAPI(
    title="Gameapy API",
    description="Retro Therapeutic Storytelling App Backend",
    version="0.1.0"
)

@app.on_event("startup")
async def startup_event():
    global db

    # Initialize database (applies base schema via _ensure_schema)
    logger.info("=" * 60)
    logger.info("Initializing database with base schema...")
    logger.info("=" * 60)
    db = Database(db_path)
    logger.info(f"Database initialized: {db_path}")

    # Now run migrations on startup (after base schema is applied)
    from migrations.run_migrations import run_all_migrations

    # Execute migrations
    logger.info("=" * 60)
    logger.info("Running database migrations on startup...")
    logger.info("=" * 60)
    run_all_migrations()

    # Auto-seed personas if none exist
    from utils.seed_personas_auto import ensure_personas_sealed
    logger.info("=" * 60)
    logger.info("Checking for persona seeding...")
    logger.info("=" * 60)
    ensure_personas_sealed(db_path)

    logger.info("=" * 60)
    logger.info("Gameapy API startup complete")
    logger.info("=" * 60)

# Now import routers (after database is fully initialized)
from app.api.gameapy import router as gameapy_router
from app.api.chat import router as chat_router
from app.api.cards import router as cards_router
from app.api.guide import router as guide_router
from app.api.session_analyzer import router as session_analyzer_router

# Configure CORS for Flutter development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",          # Local dev (default Vite)
        "http://localhost:5176",          # Local dev (current port)
        "https://gameapy-web.vercel.app", # Production Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    start_time = time.time()
    backend_status = {"status": "up", "latency_ms": round((time.time() - start_time) * 1000, 2)}

    db_start_time = time.time()
    db_status = {"status": "down", "latency_ms": None}
    try:
        # Check if db is initialized
        if db is None:
            db_status = {"status": "initializing", "latency_ms": None}
        else:
            with db._get_connection() as conn:
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()
            db_status = {"status": "up", "latency_ms": round((time.time() - db_start_time) * 1000, 2)}
    except Exception as e:
        db_status = {"status": "down", "latency_ms": None, "error": str(e)}

    # Overall status: healthy if backend is up, even if db is still initializing or down
    # This allows Railway healthcheck to pass during startup or if volume mount is delayed
    overall_status = "healthy" if backend_status["status"] == "up" else "down"
    if db_status.get("status") == "initializing":
        overall_status = "healthy"  # Return healthy during initialization
    elif db_status["latency_ms"] and db_status["latency_ms"] > 500:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {
            "backend": backend_status,
            "database": db_status
        }
    }

# Include API routes
app.include_router(gameapy_router, prefix="/api/v1", tags=["gameapy"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(cards_router)
app.include_router(guide_router)
app.include_router(session_analyzer_router)

@app.get("/")
async def root():
    return {"message": "Gameapy API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)