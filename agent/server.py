from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.orchestrator import AgentOrchestrator


app = FastAPI(
    title="Adith AI Studio - Agent Engine",
    description="Agent Reasoning Loop & SSE Streaming Service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_global_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
    return _global_orchestrator


class IndexRequest(BaseModel):
    workspace_id: str = Field(..., description="Unique ID of the workspace")
    workspace_root: str = Field(..., description="Root directory on disk to index")


class ChatRequest(BaseModel):
    workspace_id: str = Field(..., description="Unique ID of the workspace")
    prompt: str = Field(..., min_length=1, description="User instruction or prompt")
    workspace_root: Optional[str] = Field(None, description="Root directory on disk for file context")
    model: Optional[str] = Field("claude-3-5-sonnet", description="Model name")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "adith-ai-agent"}


@app.post("/v1/agent/index")
def index_workspace(
    req: IndexRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    if not os.path.isdir(req.workspace_root):
        raise HTTPException(
            status_code=400,
            detail=f"Path '{req.workspace_root}' is not a valid directory",
        )
    result = orchestrator.indexer.index_workspace(
        workspace_root=req.workspace_root,
        workspace_id=req.workspace_id,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@app.post("/v1/agent/chat")
async def chat_stream(
    req: ChatRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
):
    async def event_generator():
        async for event in orchestrator.process_prompt(
            workspace_id=req.workspace_id,
            prompt=req.prompt,
            workspace_root=req.workspace_root,
            model=req.model or "claude-3-5-sonnet",
        ):
            event_type = event.get("type", "message")
            event_json = json.dumps(event)
            yield f"event: {event_type}\ndata: {event_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent.server:app", host="0.0.0.0", port=5050, reload=False)
