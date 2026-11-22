"""
ADITH AI STUDIO - Multi-Provider LLM Integration Engine
Supports:
- Google Gemini (Free & Ultra Fast)
- OpenAI (GPT-4o, GPT-4o-mini)
- DeepSeek (DeepSeek-R1, DeepSeek-V3)
- Anthropic (Claude 3.5 Sonnet)
- Groq (Llama 3.3 70B @ 300 token/sec)
- Local Ollama (100% Offline)
- Built-in Smart Conversational Engine (when no API key is set)
"""

from .client import LLMClient, get_default_llm_client

__all__ = ["LLMClient", "get_default_llm_client"]
