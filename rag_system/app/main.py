"""
Main FastAPI Application - Harare Municipal RAG System v2.2
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
from datetime import datetime

# Custom formatter to remove emojis for Windows compatibility
class NoEmojiFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        emoji_replacements = {
            "🚀": "[START]", "📅": "[DATE]", "📁": "[DIR]", "💾": "[DATA]",
            "🧠": "[MODEL]", "❌": "[ERROR]", "✅": "[OK]", "⚠️": "[WARN]",
            "🔍": "[SEARCH]", "📊": "[STATS]", "✂️": "[CHUNK]", "📄": "[DOC]",
            "🧹": "[CLEAN]", "🧪": "[TEST]", "💡": "[INFO]", "🔥": "[HOT]",
            "🎯": "[TARGET]", "⚡": "[FAST]", "🔄": "[UPDATE]", "🔧": "[FIX]",
            "🛑": "[STOP]", "🏥": "[HEALTH]", "📚": "[DOCS]"
        }
        for emoji, text in emoji_replacements.items():
            message = message.replace(emoji, text)
        return message

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = NoEmojiFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI(
    title="Harare Municipal RAG System",
    description="Production-grade RAG system for Harare City Council v2.2",
    version="2.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app.api.query import router as query_router
from app.api.ingest import router as ingest_router
from app.api.health import router as health_router
from app.api.admin import router as admin_router

app.include_router(query_router, prefix="/api/v1", tags=["query"])
app.include_router(ingest_router, prefix="/api/v1", tags=["ingestion"])
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])

logger.info("[OK] All routers loaded successfully")

@app.on_event("startup")
async def startup_event():
    logger.info("[START] Harare Municipal RAG System v2.2 starting...")
    from app.config import config
    logger.info(f"[DIR] Documents directory: {config.DOCUMENTS_DIR}")
    logger.info(f"[DATA] Data directory: {config.DATA_DIR}")
    logger.info(f"[MODEL] Embedding model: {config.EMBEDDING_MODEL}")

    # Pre‑load embedding model to avoid first‑request delay
    try:
        from app.core.embedder import EmbeddingModel
        EmbeddingModel()  # loads the model
        logger.info("[MODEL] Embedding model pre‑loaded")
    except Exception as e:
        logger.error(f"[MODEL] Failed to pre‑load embedding model: {e}")

@app.get("/")
async def root():
    return {
        "service": "Harare Municipal RAG System",
        "version": "2.2.0",
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "health": "/api/v1/health",
            "query": "POST /api/v1/query",
            "ingest": "POST /api/v1/ingest",
            "admin": "/api/v1/admin"
        }
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)