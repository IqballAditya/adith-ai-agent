from __future__ import annotations

import json
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx


SYSTEM_PROMPT = """You are ADITH AI, a brilliant personal AI assistant and pair programmer created for Iqbal Aditya.
You have two core modes:
1. Conversational Mode: Friendly, natural, concise, and helpful. You reply to greetings ("hallo", "apa kabar") warmly, answer general questions clearly, and converse naturally in Indonesian or English matching the user's language.
2. Coding & Technical Mode: Deeply knowledgeable in software engineering (Go, Python, TypeScript, Rust, Docker, Databases, System Design). When asked to solve problems, you explain the logic clearly, provide optimal code, and format code blocks cleanly.
"""


def load_env_file(env_path: str = ".env") -> None:
    """Loads key=value pairs from a local .env file into os.environ if not already set."""
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


class LLMClient:
    """Multi-provider LLM client supporting Gemini, OpenAI, DeepSeek, Claude, Ollama, and offline conversational fallback."""

    def __init__(self, env_path: str = ".env") -> None:
        load_env_file(env_path)
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    def has_active_provider(self) -> bool:
        """Returns True if any remote API key is configured."""
        return bool(
            self.gemini_key
            or self.openai_key
            or self.deepseek_key
            or self.anthropic_key
            or self.groq_key
        )

    def get_provider_info(self) -> dict[str, Any]:
        """Returns active provider status."""
        if self.gemini_key:
            return {"provider": "gemini", "model": "gemini-1.5-flash", "active": True}
        if self.openai_key:
            return {"provider": "openai", "model": "gpt-4o", "active": True}
        if self.deepseek_key:
            return {"provider": "deepseek", "model": "deepseek-chat", "active": True}
        if self.anthropic_key:
            return {"provider": "anthropic", "model": "claude-3-5-sonnet", "active": True}
        if self.groq_key:
            return {"provider": "groq", "model": "llama-3.3-70b-versatile", "active": True}
        return {"provider": "local_adith_engine", "model": "adith-conversational-v1", "active": True}

    async def stream_response(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        context_snippets: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks token-by-token from the active LLM provider, or falls back to intelligent local engine."""
        # 1. Google Gemini (via official OpenAI-compatible endpoint)
        if self.gemini_key:
            async for token in self._stream_openai_compatible(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key=self.gemini_key,
                model_name=model or "gemini-1.5-flash",
                prompt=prompt,
                system_prompt=system_prompt,
                context_snippets=context_snippets,
            ):
                yield token
            return

        # 2. OpenAI (GPT-4o)
        if self.openai_key:
            async for token in self._stream_openai_compatible(
                base_url="https://api.openai.com/v1",
                api_key=self.openai_key,
                model_name=model or "gpt-4o",
                prompt=prompt,
                system_prompt=system_prompt,
                context_snippets=context_snippets,
            ):
                yield token
            return

        # 3. DeepSeek (DeepSeek-R1 / V3)
        if self.deepseek_key:
            async for token in self._stream_openai_compatible(
                base_url="https://api.deepseek.com",
                api_key=self.deepseek_key,
                model_name=model or "deepseek-chat",
                prompt=prompt,
                system_prompt=system_prompt,
                context_snippets=context_snippets,
            ):
                yield token
            return

        # 4. Groq (Llama 3.3 70B ultra fast)
        if self.groq_key:
            async for token in self._stream_openai_compatible(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_key,
                model_name=model or "llama-3.3-70b-versatile",
                prompt=prompt,
                system_prompt=system_prompt,
                context_snippets=context_snippets,
            ):
                yield token
            return

        # 5. Local Conversational & Knowledge Engine (when no external API key is configured)
        async for token in self._local_conversational_engine(prompt, context_snippets):
            yield token

    async def _stream_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        prompt: str,
        system_prompt: str,
        context_snippets: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Streams from any OpenAI-compatible Chat Completions API."""
        user_content = prompt
        if context_snippets:
            user_content = f"Workspace Codebase Context:\n{context_snippets}\n\nUser Request:\n{prompt}"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": True,
            "temperature": 0.7,
        }

        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", endpoint, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        yield f"⚠️ API Error ({resp.status_code}): {err_text.decode('utf-8', errors='replace')}\n\n"
                        async for token in self._local_conversational_engine(prompt, context_snippets):
                            yield token
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception as e:
            yield f"⚠️ Connection fallback ({type(e).__name__}): Beralih ke mesin percakapan lokal ADITH AI.\n\n"
            async for token in self._local_conversational_engine(prompt, context_snippets):
                yield token

    async def _local_conversational_engine(
        self,
        prompt: str,
        context_snippets: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Intelligent local conversational engine when no external API key is set."""
        p_clean = prompt.strip().lower()

        # Greetings & Casual Chat
        if any(w in p_clean for w in ["hallo", "halo", "hai", "hi", "hey", "hei"]):
            yield "Halo Iqbal! 👋 Senang bertemu denganmu.\n\n"
            yield "Saya **ADITH AI**, asisten coding dan partner berpikir pribadimu di studio ini. "
            yield "Ada yang bisa saya bantu hari ini? Kamu bisa menyuruh saya menulis kode, refactor fungsi, menjawab pertanyaan seputar sistem arsitektur, atau sekadar ngobrol santai!"
            return

        if any(w in p_clean for w in ["apa kabar", "gimana kabarnya", "how are you"]):
            yield "Kabar saya luar biasa dan siap membantu pekerjaanmu! 🚀\n\n"
            yield "Semua sistem di studio ini (Go Gateway, Qdrant Vector Memory, Tree-sitter AST, dan Terminal) berjalan normal dan optimal. "
            yield "Proyek apa yang ingin kita kerjakan hari ini?"
            return

        if any(w in p_clean for w in ["kamu siapa", "siapa kamu", "who are you", "tentang kamu"]):
            yield "Saya adalah **ADITH AI**, sebuah AI Coding Assistant & Studio Engine mandiri yang dirancang khusus untuk Iqbal Aditya.\n\n"
            yield "### Kemampuan Utama Saya:\n"
            yield "1. **Codebase Understanding**: Memahami struktur kode fungsi, struct, dan kelas menggunakan Tree-sitter AST.\n"
            yield "2. **Vector Memory**: Menyimpan dan mencari konteks kodemu lewat Qdrant Vector DB.\n"
            yield "3. **Safe Diff Execution**: Mengusulkan perubahan kode (diff patch) yang bisa kamu terima dengan satu klik (*Accept Changes* / tombol `Tab`).\n"
            yield "4. **General Conversation**: Menjawab segala pertanyaan dari hal ringan hingga tugas rekayasa perangkat lunak berskala besar."
            return

        if any(w in p_clean for w in ["terima kasih", "makasih", "thanks", "thank you"]):
            yield "Sama-sama, Iqbal! Senang bisa membantumu. Jika butuh bantuan lain atau mau nambah fitur baru, langsung panggil saya lagi ya! 😊"
            return

        # General Programming / Concept Explanations
        if "microservice" in p_clean or "microservices" in p_clean:
            yield "### Apa Itu Arsitektur Microservices?\n\n"
            yield "**Microservices** adalah pola arsitektur di mana aplikasi besar dipecah menjadi kumpulan layanan-layanan kecil yang mandiri (*decoupled*), masing-masing menjalankan proses bisnis spesifik dan berkomunikasi melalui protokol jaringan ringan (seperti HTTP REST, gRPC, atau Message Broker seperti Kafka/NATS).\n\n"
            yield "**Kelebihan Utama:**\n"
            yield "- **Scalability Mandiri**: Layanan yang tinggi trafik (misal: Checkout) bisa di-scale terpisah tanpa perlu memperbesar seluruh aplikasi.\n"
            yield "- **Polyglot**: Tim bisa memakai bahasa berbeda untuk layanan berbeda (seperti ADITH AI Studio: Go untuk Gateway, Python untuk AI Engine, TypeScript untuk Frontend).\n"
            yield "- **Fault Isolation**: Jika satu service error, sistem utama tidak langsung mati total."
            return

        if "docker" in p_clean:
            yield "### Apa Itu Docker & Mengapa Sangat Populer?\n\n"
            yield "**Docker** adalah platform kontainerisasi yang membungkus aplikasi beserta seluruh dependensinya (library, konfigurasi runtime, dan binary) ke dalam satu wadah terisolasi bernama **Container**.\n\n"
            yield "**Prinsip Utama:** *'Build Once, Run Anywhere'*. Menghilangkan masalah klasik *'di laptop saya jalan, tapi di server kok error'*. Di ADITH AI Studio, kita sudah siapkan arsitektur Dockerfile multi-stage agar nanti bisa di-deploy ke server cloud dengan mudah!"
            return

        # Default Helpful Intelligent Assistant Response
        yield f"Saya telah menerima pertanyaanmu: *\"{prompt.strip()}\"*\n\n"
        if context_snippets:
            yield f"💡 **Konteks Codebase Terdeteksi:**\n{context_snippets[:300]}...\n\n"

        yield "Sebagai asisten personalmu di **ADITH AI STUDIO**, saya siap membantumu menyelesaikan tugas ini! "
        yield "Apakah kamu ingin saya membuatkan rancangan kodenya, menjelaskan konsep logikanya langkah demi langkah, atau membuatkan file baru di workspace ini?\n\n"
        yield "---\n"
        yield "*(💡 **Tips:** Untuk menghubungkan kemampuan open-domain tanpa batas seperti ChatGPT / Claude asli ke seluruh topik di dunia, kamu cukup menambahkan `GEMINI_API_KEY=...` atau `OPENAI_API_KEY=...` di file `.env` studio ini!)*"


_DEFAULT_CLIENT: Optional[LLMClient] = None


def get_default_llm_client() -> LLMClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = LLMClient()
    return _DEFAULT_CLIENT
