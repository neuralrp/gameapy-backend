from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.api.gameapy import router as gameapy_router
from app.api.chat import router as chat_router
from app.api.cards import router as cards_router
from app.api.guide import router as guide_router
from app.api.session_analyzer import router as session_analyzer_router

app = FastAPI(
    title="Gameapy API",
    description="Retro Therapeutic Storytelling App Backend",
    version="0.1.0"
)

# Configure CORS for Flutter development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",          # Local dev (default Vite)
        "http://localhost:5176",          # Local dev (current port)
        "https://gameapy.vercel.app",     # Production Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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