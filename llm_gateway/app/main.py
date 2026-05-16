"""
Harare City Council LLM Gateway v6.0 – Orchestrator based entry point.
"""

import time
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
import uvicorn
import logging
import sys
import yaml
import os
import httpx
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from .orchestrator import Orchestrator
from .models import ChatRequest, ChatResponse
from .override_manager import override_manager
from .knowledge_gap_logger import KnowledgeGapLogger, gap_logger as global_gap_logger

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Harare City Council LLM Gateway", version="6.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Load config
with open("gateway_config.yaml", 'r', encoding='utf-8') as f:
    full_config = yaml.safe_load(f)
config = full_config['llm_gateway']

# Initialize knowledge gap logger
dashboard_config = config.get("dashboard", {})
gap_logger_instance = KnowledgeGapLogger(
    dashboard_url=dashboard_config.get("url", "http://localhost:5000"),
    api_key=dashboard_config.get("api_key", "")
)
global_gap_logger = gap_logger_instance
import sys
sys.modules['app.knowledge_gap_logger'].gap_logger = gap_logger_instance

logger.info("Knowledge gap logger initialised with dashboard URL: {}".format(dashboard_config.get("url")))

orchestrator = Orchestrator(config)

class FeedbackRequest(BaseModel):
    question: str
    user_id: str
    feedback_type: str
    details: Optional[str] = None
    session_id: Optional[str] = None

@app.on_event("startup")
async def startup():
    logger.info("LLM Gateway v6.0 starting...")
    # Configure override manager with dashboard settings
    override_manager.dashboard_config = dashboard_config
    # Start periodic sync (every 60 seconds)
    asyncio.create_task(override_manager.start_periodic_sync(interval_seconds=60))
    logger.info("Override sync background task started")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    start_time = time.time()
    session_id = request.session_id or f"{request.source}_{request.user_id}_{int(start_time)}"
    try:
        result = await orchestrator.handle(
            message=request.message,
            session_id=session_id,
            user_id=request.user_id,
            source=request.source
        )
        return ChatResponse(
            response=result["response"],
            intent=result.get("intent", "knowledge_query"),
            source=result.get("source", "orchestrator"),
            metadata={
                "response_time": time.time() - start_time,
                "cached": result.get("cached", False),
                "governed": result.get("governed", False)
            },
            session_id=session_id
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        return ChatResponse(
            response="I'm sorry, something went wrong. Please try again.",
            intent="error",
            source="error",
            metadata={"response_time": time.time() - start_time},
            session_id=session_id
        )

@app.post("/override")
async def create_override(
    override_type: str,
    target_type: str,
    target_value: str,
    authority_name: str,
    authority_role: str,
    override_reason: str,
    expires_at: Optional[str] = None
):
    try:
        expires_dt = None
        if expires_at:
            if expires_at.endswith('Z'):
                expires_at = expires_at[:-1] + '+00:00'
            expires_dt = datetime.fromisoformat(expires_at)
        override_id = override_manager.create_override(
            override_type=override_type,
            target_type=target_type,
            target_value=target_value,
            authority_name=authority_name,
            authority_role=authority_role,
            override_reason=override_reason,
            expires_at=expires_dt
        )
        return {"status": "override_created", "override_id": override_id}
    except Exception as e:
        logger.error(f"Override creation failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.post("/knowledge_gap_feedback")
async def knowledge_gap_feedback(request: FeedbackRequest):
    try:
        if global_gap_logger:
            await global_gap_logger.log_gap(
                question=request.question,
                response="",
                user_id=request.user_id,
                session_id=request.session_id or "unknown",
                source="user_feedback",
                confidence=0.0,
                metadata={"feedback_type": request.feedback_type, "details": request.details}
            )
        return {"status": "feedback_received"}
    except ValidationError as e:
        logger.error(f"Feedback validation error: {e}")
        return {"status": "error", "message": "Invalid request body", "details": e.errors()}, 422
    except Exception as e:
        logger.error(f"Feedback logging failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.post("/webhook/rasa")
async def rasa_webhook(request: Request):
    try:
        data = await request.json()
        dashboard_url = config.get("dashboard", {}).get("url", "http://localhost:5000")
        api_key = config.get("dashboard", {}).get("api_key", "")
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var, "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        if data.get("event_type") == "report_confirmed" and "payload" in data:
            payload = data["payload"]
            transformed = {
                "raw_text": payload.get("raw_text"),
                "landmark": payload.get("landmark"),
                "citizen_session_id": payload.get("citizen_session_id"),
                "spam_flag": payload.get("spam_flag", False),
                "spam_reason": payload.get("spam_reason"),
                "timestamp": payload.get("timestamp"),
                "standardized_type": data.get("standardized_type"),
                "standardized_location": data.get("standardized_location"),
                "urgency": data.get("urgency", "medium"),
            }
            transformed = {k: v for k, v in transformed.items() if v is not None}
        else:
            transformed = data
        logger.info(f"Forwarding report to Dashboard: {dashboard_url}/api/reports")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{dashboard_url}/api/reports",
                json=transformed,
                headers=headers
            )
            if resp.status_code in (200, 201):
                return JSONResponse(resp.json(), status_code=resp.status_code)
            else:
                logger.error(f"Dashboard returned {resp.status_code}: {resp.text}")
                return JSONResponse(
                    {"error": "Dashboard failed to create report", "status": resp.status_code},
                    status_code=502
                )
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    active_sessions = orchestrator.session.get_active_session_count()
    avg_response = orchestrator.get_avg_response_time()
    return {
        "status": "healthy",
        "version": "6.0.0",
        "orchestrator": "active",
        "active_sessions": active_sessions,
        "avg_response_time": round(avg_response, 2)
    }

@app.get("/")
async def root():
    return {
        "service": "Harare City Council LLM Gateway",
        "version": "6.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
        timeout_keep_alive=600      # <-- ADDED: Prevents connection drops during long LLM generation
    )