from __future__ import annotations

import json
import os
import tempfile
from typing import AsyncGenerator
import pytest
from fastapi.testclient import TestClient

from agent.memory import VectorStore
from agent.orchestrator import AgentOrchestrator
from agent.parser import ASTParser
from agent.server import app, get_orchestrator


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        main_py = os.path.join(tmpdir, "main.py")
        with open(main_py, "w", encoding="utf-8") as f:
            f.write(
                "def calculate_total(items):\n"
                "    total = 0\n"
                "    for item in items:\n"
                "        total += item['price']\n"
                "    return total\n"
            )
        yield tmpdir


@pytest.fixture
def test_vector_store():
    store = VectorStore(storage_path=":memory:", collection_name="test_orchestrator")
    yield store
    store.close()


@pytest.fixture
def test_orchestrator(test_vector_store):
    return AgentOrchestrator(vector_store=test_vector_store)


@pytest.fixture
def client(test_orchestrator):
    app.dependency_overrides[get_orchestrator] = lambda: test_orchestrator
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def parse_sse_events(raw_sse_text: str) -> list[dict]:
    """Parse raw SSE text into structured list of (event_type, json_data)."""
    events = []
    blocks = raw_sse_text.strip().split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        event_type = None
        data_str = None
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_str = line[len("data:") :].strip()
        if event_type and data_str:
            events.append({"event": event_type, "data": json.loads(data_str)})
    return events


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok", "service": "adith-ai-agent"}


def test_index_endpoint(client, temp_workspace):
    response = client.post(
        "/v1/agent/index",
        json={"workspace_id": "test-ws-1", "workspace_root": temp_workspace},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == "test-ws-1"
    assert data["status"] == "success"
    assert data["files_indexed"] >= 1
    assert data["symbols_indexed"] >= 1


def test_index_endpoint_invalid_path(client):
    response = client.post(
        "/v1/agent/index",
        json={"workspace_id": "test-ws-err", "workspace_root": "C:/nonexistent/invalid/dir"},
    )
    assert response.status_code == 400 or response.json().get("status") == "error"


@pytest.mark.anyio
async def test_orchestrator_process_prompt_direct(test_orchestrator, temp_workspace):
    # Index workspace first
    test_orchestrator.indexer.index_workspace(temp_workspace, "test-ws-2")

    events = []
    async for evt in test_orchestrator.process_prompt(
        workspace_id="test-ws-2",
        prompt="Fix bug in calculate_total to handle empty items list",
        workspace_root=temp_workspace,
    ):
        events.append(evt)

    types = [e["type"] for e in events]
    assert "reasoning" in types
    assert "message" in types
    assert "diff" in types
    assert "done" in types

    # Verify diff structure
    diff_event = next(e for e in events if e["type"] == "diff")
    diff_data = diff_event["data"]
    assert "path" in diff_data
    assert "original" in diff_data
    assert "modified" in diff_data
    assert "unified_diff" in diff_data
    assert "calculate_total" in diff_data["original"]
    assert "---" in diff_data["unified_diff"]
    assert "+++" in diff_data["unified_diff"]

    # Verify done event structure
    done_event = next(e for e in events if e["type"] == "done")
    assert "usage" in done_event
    assert done_event["usage"]["prompt_tokens"] > 0
    assert done_event["usage"]["completion_tokens"] > 0


def test_chat_endpoint_sse_stream(client, temp_workspace):
    # Index workspace first
    idx_resp = client.post(
        "/v1/agent/index",
        json={"workspace_id": "test-ws-chat", "workspace_root": temp_workspace},
    )
    assert idx_resp.status_code == 200

    response = client.post(
        "/v1/agent/chat",
        json={
            "workspace_id": "test-ws-chat",
            "prompt": "Fix bug in calculate_total function in main.py",
            "workspace_root": temp_workspace,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = parse_sse_events(response.text)
    event_names = [e["event"] for e in events]
    assert "reasoning" in event_names
    assert "message" in event_names
    assert "diff" in event_names
    assert "done" in event_names

    diff_item = next(e for e in events if e["event"] == "diff")
    assert "data" in diff_item["data"]
    assert "unified_diff" in diff_item["data"]["data"]


def test_chat_endpoint_conversational_query(client, temp_workspace):
    response = client.post(
        "/v1/agent/chat",
        json={
            "workspace_id": "test-ws-chat",
            "prompt": "Explain what this project does and how calculate_total works",
            "workspace_root": temp_workspace,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    events = parse_sse_events(response.text)
    event_names = [e["event"] for e in events]
    assert "reasoning" in event_names
    assert "message" in event_names
    assert "done" in event_names


def test_diff_generation_new_file(test_orchestrator, temp_workspace):
    events = []

    async def run():
        async for evt in test_orchestrator.process_prompt(
            workspace_id="test-ws-new",
            prompt="Create new file math_helper.py with add function",
            workspace_root=temp_workspace,
        ):
            events.append(evt)

    import anyio
    anyio.run(run)

    diff_events = [e for e in events if e["type"] == "diff"]
    assert len(diff_events) >= 1
    diff_data = diff_events[0]["data"]
    assert diff_data["path"] == "math_helper.py"
    assert diff_data["original"] == ""
    assert "def add" in diff_data["modified"] or "add" in diff_data["modified"]
    assert "+++" in diff_data["unified_diff"]


def test_chat_endpoint_validation_error(client):
    response = client.post("/v1/agent/chat", json={})
    assert response.status_code == 422


def test_orchestrator_custom_mock_adapter():
    class CustomMockLLM:
        async def process_prompt(self, workspace_id: str, prompt: str, **kwargs):
            yield {"type": "reasoning", "content": "custom mock reasoning"}
            yield {"type": "message", "content": "custom mock message"}
            yield {"type": "done", "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

    store = VectorStore(storage_path=":memory:", collection_name="mock_test")
    orchestrator = AgentOrchestrator(vector_store=store, llm_adapter=CustomMockLLM())

    events = []

    async def run():
        async for evt in orchestrator.process_prompt("mock-ws", "mock prompt"):
            events.append(evt)

    import anyio
    anyio.run(run)

    assert len(events) == 3
    assert events[0]["content"] == "custom mock reasoning"
    assert events[1]["content"] == "custom mock message"
    assert events[2]["type"] == "done"
    store.close()
