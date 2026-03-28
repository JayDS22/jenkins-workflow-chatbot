"""
FastAPI Backend - Jenkins Workflow Chatbot PoC (v2 - Enhanced)

Upgrades over v1:
  - RAG integration: agents now get relevant Jenkins docs alongside live context
  - Rich demo mode: realistic build logs, multiple failure types, compelling
    without a Jenkins instance
  - Conversation history: maintains context within a session
  - Better error handling and response metadata
  - Cloud-deployment ready (serves frontend on same port, works behind proxy)

The architecture is still intentionally decoupled from Jenkins.
This runs as a standalone service - exactly how the production
GSoC plugin would work as a sidecar.
"""

import json
import asyncio
import logging
import time
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
from sse_starlette.sse import EventSourceResponse

from app.utils.jenkins_context import JenkinsContext
from app.agents.router import classify_intent
from app.agents.troubleshoot import troubleshoot
from app.agents.workflow import guide_workflow
from app.agents.recommend import recommend
from app.demo.mock_data import (
    get_demo_server_info, get_demo_build_log,
    get_demo_failed_builds, get_demo_job_details,
)

# RAG import - graceful if dependencies missing
try:
    from app.rag.engine import JenkinsRAG
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Jenkins Workflow Chatbot PoC",
    description=(
        "Context-aware multi-agent chatbot that reads live Jenkins state, "
        "retrieves relevant documentation via RAG, and provides intelligent "
        "workflow guidance, build troubleshooting, and plugin recommendations. "
        "Built by Jay Guwalani for GSoC 2026."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core components
jenkins_ctx = JenkinsContext()

# Initialize RAG engine (loads embeddings + FAISS index)
rag_engine = None
if _RAG_AVAILABLE:
    try:
        rag_engine = JenkinsRAG()
    except Exception as e:
        logger.warning(f"RAG engine failed to initialize: {e}")

# Simple in-memory conversation history (per session, resets on restart)
# In production this would use Redis or a database
conversation_history: dict[str, list] = {}


# --------------------------------------------------------------------------
# Request/Response Models
# --------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    job_name: Optional[str] = Field(None, description="Specific Jenkins job to focus on")
    build_number: Optional[int] = Field(None, description="Specific build number to analyze")
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")


class ChatResponse(BaseModel):
    query: str
    intent: str
    job_context: Optional[str]
    jenkins_connected: bool
    demo_mode: bool
    response: str
    rag_sources: list = []
    response_time_ms: int


# --------------------------------------------------------------------------
# Serve frontend on the same port (enables single-command cloud deployment)
# --------------------------------------------------------------------------

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(frontend_dir):
    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend")


# --------------------------------------------------------------------------
# Health & Jenkins Context Endpoints
# --------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "jenkins-workflow-chatbot",
        "version": "0.2.0",
        "jenkins_connected": jenkins_ctx.is_connected,
        "demo_mode": not jenkins_ctx.is_connected,
        "rag_enabled": rag_engine is not None and rag_engine.is_ready,
        "rag_docs": rag_engine.doc_count if rag_engine else 0,
        "rag_vector_search": rag_engine.using_vectors if rag_engine else False,
    }


@app.get("/api/jenkins/info")
def get_jenkins_info():
    if jenkins_ctx.is_connected:
        return jenkins_ctx.get_server_info()
    return get_demo_server_info()


@app.get("/api/jenkins/jobs/{job_name}")
def get_job_info(job_name: str):
    if jenkins_ctx.is_connected:
        result = jenkins_ctx.get_job_details(job_name)
    else:
        result = get_demo_job_details(job_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/jenkins/jobs/{job_name}/builds/{build_number}/log")
def get_build_log_endpoint(job_name: str, build_number: int):
    if jenkins_ctx.is_connected:
        result = jenkins_ctx.get_build_log(job_name, build_number)
    else:
        result = get_demo_build_log(job_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/jenkins/failed")
def get_failed_builds():
    if jenkins_ctx.is_connected:
        return jenkins_ctx.get_failed_builds_summary()
    return get_demo_failed_builds()


# --------------------------------------------------------------------------
# RAG Search Endpoint (test retrieval directly)
# --------------------------------------------------------------------------

@app.get("/api/rag/search")
def rag_search(q: str, top_k: int = 3):
    """Test the RAG retrieval independently - useful for debugging."""
    if not rag_engine or not rag_engine.is_ready:
        return {"error": "RAG engine not available", "results": []}
    results = rag_engine.retrieve(q, top_k=top_k)
    return {"query": q, "using_vectors": rag_engine.using_vectors, "results": results}


# --------------------------------------------------------------------------
# Main Chat Endpoint
# --------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    start = time.time()

    server_info = jenkins_ctx.get_server_info() if jenkins_ctx.is_connected else get_demo_server_info()
    demo_mode = not jenkins_ctx.is_connected

    context_summary = (
        f"Jenkins {server_info.get('jenkins_version', 'unknown')}, "
        f"{server_info.get('job_count', 0)} jobs, "
        f"{server_info.get('plugin_count', 0)} plugins"
    )
    if req.job_name:
        context_summary += f", focused on job: {req.job_name}"

    logger.info(f"Chat: '{req.query}' | Job: {req.job_name} | Demo: {demo_mode}")

    intent = classify_intent(req.query, context_summary)
    logger.info(f"Intent: {intent}")

    # RAG retrieval
    rag_context, rag_sources = _get_rag_context(req.query)

    # Route to agent
    if intent == "TROUBLESHOOT":
        response = _handle_troubleshoot(req, server_info, demo_mode, rag_context)
    elif intent == "WORKFLOW":
        response = _handle_workflow(req.query, server_info, rag_context)
    elif intent == "RECOMMEND":
        response = _handle_recommend(req.query, server_info, rag_context)
    else:
        response = _handle_general(req.query, rag_context)

    elapsed_ms = int((time.time() - start) * 1000)

    if req.session_id:
        conversation_history.setdefault(req.session_id, []).append(
            {"query": req.query, "intent": intent, "response": response[:500]}
        )

    return ChatResponse(
        query=req.query,
        intent=intent,
        job_context=req.job_name,
        jenkins_connected=jenkins_ctx.is_connected,
        demo_mode=demo_mode,
        response=response,
        rag_sources=rag_sources,
        response_time_ms=elapsed_ms,
    )


# --------------------------------------------------------------------------
# SSE Streaming Endpoint
# --------------------------------------------------------------------------

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        start = time.time()

        server_info = jenkins_ctx.get_server_info() if jenkins_ctx.is_connected else get_demo_server_info()
        demo_mode = not jenkins_ctx.is_connected

        context_summary = f"Jenkins {server_info.get('jenkins_version', 'unknown')}, {server_info.get('job_count', 0)} jobs"
        intent = classify_intent(req.query, context_summary)

        yield {"event": "intent", "data": json.dumps({"intent": intent})}
        yield {"event": "context", "data": json.dumps({
            "jenkins_version": server_info.get("jenkins_version"),
            "job_count": server_info.get("job_count"),
            "plugin_count": server_info.get("plugin_count"),
            "connected": server_info.get("connected", False),
            "demo_mode": demo_mode,
        })}

        rag_context, rag_sources = _get_rag_context(req.query)
        if rag_sources:
            yield {"event": "rag", "data": json.dumps({"sources": rag_sources})}

        if intent == "TROUBLESHOOT":
            response = _handle_troubleshoot(req, server_info, demo_mode, rag_context)
        elif intent == "WORKFLOW":
            response = _handle_workflow(req.query, server_info, rag_context)
        elif intent == "RECOMMEND":
            response = _handle_recommend(req.query, server_info, rag_context)
        else:
            response = _handle_general(req.query, rag_context)

        elapsed_ms = int((time.time() - start) * 1000)
        yield {"event": "response", "data": json.dumps({"response": response, "response_time_ms": elapsed_ms})}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get_rag_context(query: str) -> tuple[str, list]:
    """Retrieve relevant docs from RAG engine."""
    if not rag_engine or not rag_engine.is_ready:
        return "", []

    docs = rag_engine.retrieve(query, top_k=3)
    if not docs:
        return "", []

    rag_context = "\n\n".join([f"[Doc: {d['title']}] {d['content']}" for d in docs])
    rag_sources = [{"title": d["title"], "source": d["source"], "score": round(d["score"], 3)} for d in docs]
    return rag_context, rag_sources


def _handle_troubleshoot(req: ChatRequest, server_info: dict, demo_mode: bool, rag_context: str) -> str:
    if jenkins_ctx.is_connected and req.job_name:
        build_data = jenkins_ctx.get_build_log(req.job_name, req.build_number)
    elif jenkins_ctx.is_connected:
        failed = jenkins_ctx.get_failed_builds_summary()
        if failed:
            build_data = jenkins_ctx.get_build_log(failed[0]["job_name"], failed[0]["failed_build_number"])
        else:
            build_data = _empty_build()
    elif req.job_name:
        build_data = get_demo_build_log(req.job_name)
    else:
        failed = get_demo_failed_builds()
        build_data = get_demo_build_log(failed[0]["job_name"]) if failed else _empty_build()

    enriched = req.query + (f"\n\n[Reference docs:\n{rag_context}]" if rag_context else "")
    return troubleshoot(enriched, build_data, server_info.get("installed_plugins", []))


def _handle_workflow(query: str, server_info: dict, rag_context: str) -> str:
    enriched = query + (f"\n\n[Reference docs:\n{rag_context}]" if rag_context else "")
    return guide_workflow(enriched, server_info)


def _handle_recommend(query: str, server_info: dict, rag_context: str) -> str:
    enriched = query + (f"\n\n[Reference docs:\n{rag_context}]" if rag_context else "")
    return recommend(enriched, server_info)


def _handle_general(query: str, rag_context: str) -> str:
    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)
        prompt = "You are a helpful Jenkins assistant. Be concise and practical.\n\n"
        if rag_context:
            prompt += f"Relevant documentation:\n{rag_context}\n\n"
        prompt += f"Question: {query}"
        return llm.invoke(prompt).content
    except Exception as e:
        return f"I couldn't process that question: {str(e)}"


def _empty_build() -> dict:
    return {"job_name": "unknown", "build_number": None, "result": "unknown",
            "error_lines": [], "console_tail": "No failed builds found."}


# --------------------------------------------------------------------------
# Startup
# --------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    if jenkins_ctx.is_connected:
        info = jenkins_ctx.get_server_info()
        logger.info(f"Jenkins connected: v{info.get('jenkins_version')}, {info.get('job_count')} jobs, {info.get('plugin_count')} plugins")
    else:
        logger.info("Jenkins not connected - DEMO MODE active with realistic mock data")

    if rag_engine and rag_engine.is_ready:
        mode = "vector search (FAISS)" if rag_engine.using_vectors else "keyword fallback"
        logger.info(f"RAG engine: {rag_engine.doc_count} docs ({mode})")

    logger.info("Jenkins Workflow Chatbot PoC v2 ready")
    logger.info("  API docs: http://localhost:8000/docs")
    logger.info("  Frontend: http://localhost:8000/")
