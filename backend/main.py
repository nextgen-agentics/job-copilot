"""
main.py — JobCopilot AI FastAPI Backend
==========================================
Endpoints:
  POST /analyze         — SSE stream of agent reasoning chain
  POST /profile/resume  — Upload & parse PDF resume
  POST /profile/github  — Fetch & cache GitHub profile
  PUT  /profile/prefs   — Update preferences + model selection
  GET  /profile         — Get current profile
  GET  /health          — Health check
"""
import json
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from agent import run_agent
from tools.resume_parser import parse_resume, set_model as set_parser_model
from tools.github_parser import fetch_github_repos

load_dotenv()

app = FastAPI(title="JobCopilot AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Chrome extension origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory profile store (per-server session; extension also keeps copy in localStorage)
_profile: dict = {
    "resume": None,
    "github": None,
    "preferences": "",
    "model": "gemini-2.0-flash",
}

executor = ThreadPoolExecutor(max_workers=4)


# ──────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ──────────────────────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    query: str
    page_context: Optional[str] = ""
    profile_override: Optional[dict] = None  # if extension sends its own cached profile
    model: Optional[str] = None


class PrefsRequest(BaseModel):
    preferences: str
    model: Optional[str] = "gemini-2.0-flash"


# ──────────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "model": _profile["model"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Profile endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/profile")
async def get_profile():
    return {
        "has_resume": _profile["resume"] is not None,
        "has_github": _profile["github"] is not None,
        "preferences": _profile["preferences"],
        "model": _profile["model"],
        "resume_skills": _profile["resume"].get("skills", []) if _profile["resume"] else [],
        "github_username": _profile["github"].get("profile", {}).get("username") if _profile["github"] else None,
    }


@app.post("/profile/resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    pdf_bytes = await file.read()
    # Sync current model to the LLM parser before parsing
    set_parser_model(_profile.get("model", "gemini-2.0-flash"))
    parsed = parse_resume(pdf_bytes)

    # Hard error (PDF unreadable) — return 422
    if "error" in parsed and "_parsed_by" not in parsed:
        raise HTTPException(status_code=422, detail=parsed["error"])

    _profile["resume"] = parsed

    used_fallback = parsed.get("_parsed_by") == "regex_fallback"
    return {
        "message": "Resume parsed successfully" if not used_fallback else "Resume parsed (basic mode — LLM unavailable, rate limit hit)",
        "skills_found": parsed.get("skills", []),
        "pages": parsed.get("pages", 1),
        "github_detected": parsed.get("github_url"),
        "name": parsed.get("full_name"),
        "llm_used": not used_fallback,
        "warning": parsed.get("_llm_error") if used_fallback else None,
    }


@app.post("/profile/github")
async def load_github(request: Request):
    body = await request.json()
    github_url = body.get("github_url", "")
    if not github_url:
        raise HTTPException(status_code=400, detail="github_url required")

    loop = asyncio.get_event_loop()
    result_str = await loop.run_in_executor(executor, fetch_github_repos, github_url)
    result = json.loads(result_str)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    _profile["github"] = result
    return {
        "message": "GitHub profile loaded",
        "username": result.get("profile", {}).get("username"),
        "repos": len(result.get("repositories", [])),
        "ml_projects": result.get("ml_ai_projects", []),
    }


@app.put("/profile/prefs")
async def update_prefs(req: PrefsRequest):
    _profile["preferences"] = req.preferences
    if req.model:
        _profile["model"] = req.model
    return {"message": "Preferences updated", "model": _profile["model"]}


# ──────────────────────────────────────────────────────────────────────────────
# Main analyze endpoint — SSE streaming agent loop
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Run the multi-step agent and stream reasoning chain as Server-Sent Events.
    Each event is a JSON object:
      {"type": "tool_call",   "tool": "...", "args": {...}, "iteration": N}
      {"type": "tool_result", "tool": "...", "result": {...}}
      {"type": "answer",      "content": "...", "dashboard": {...}}
      {"type": "error",       "content": "..."}
      {"type": "retry",       "content": "..."}
    """
    profile = req.profile_override or _profile
    model_name = req.model or profile.get("model", "gemini-2.0-flash")

    async def event_stream():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _run():
            try:
                for event in run_agent(
                    query=req.query,
                    profile=profile,
                    page_context=req.page_context or "",
                    model_name=model_name,
                ):
                    asyncio.run_coroutine_threadsafe(queue.put(event), loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    queue.put({"type": "error", "content": str(e)}), loop
                )
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        loop.run_in_executor(executor, _run)

        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
