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


@pytest.mark.anyio
async def test_llm_conversational_prabowo():
    client = LLMClient()
    chunks = []
    async for chunk in client.stream_response("siapa itu prabowo?"):
        chunks.append(chunk)
    reply = "".join(chunks)
    assert "Prabowo Subianto" in reply
    assert "Presiden Republik Indonesia ke-8" in reply


@pytest.mark.anyio
async def test_llm_conversational_math():
    client = LLMClient()
    chunks = []
    async for chunk in client.stream_response("hitung 5 * 25"):
        chunks.append(chunk)
    reply = "".join(chunks)
    assert "125" in reply


@pytest.mark.anyio
async def test_llm_conversational_science_and_fallback():
    client = LLMClient()
    # Test science
    chunks = []
    async for chunk in client.stream_response("kenapa langit biru?"):
        chunks.append(chunk)
    reply = "".join(chunks)
    assert "Hamburan Rayleigh" in reply

    # Test open fallback (never rigid)
    chunks_open = []
    async for chunk in client.stream_response("ceritakan hal acak"):
        chunks_open.append(chunk)
    reply_open = "".join(chunks_open)
    assert "Apakah kamu ingin saya membuatkan rancangan kodenya" not in reply_open
