import pytest
from agent.llm.client import LLMClient


@pytest.mark.anyio
async def test_llm_conversational_greetings():
    client = LLMClient()
    # Test greeting
    chunks = []
    async for chunk in client.stream_response("hallo"):
        chunks.append(chunk)
    reply = "".join(chunks)
    assert "Halo" in reply
    assert "ADITH AI" in reply


@pytest.mark.anyio
async def test_llm_conversational_who_are_you():
    client = LLMClient()
    chunks = []
    async for chunk in client.stream_response("kamu siapa?"):
        chunks.append(chunk)
    reply = "".join(chunks)
    assert "ADITH AI" in reply
    assert "Tree-sitter" in reply


@pytest.mark.anyio
async def test_llm_conversational_general_concept():
    client = LLMClient()
    chunks = []
    async for chunk in client.stream_response("apa itu microservices?"):
        chunks.append(chunk)
    reply = "".join(chunks)
    assert "Microservices" in reply
