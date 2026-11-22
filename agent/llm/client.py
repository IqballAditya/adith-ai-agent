from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx


SYSTEM_PROMPT = """You are ADITH AI, a brilliant, friendly, and helpful personal AI assistant created for Iqbal Aditya.
You answer any question naturally and warmly in Indonesian or English matching the user's prompt.
You are never rigid or robotic. If asked general knowledge (like history, figures, casual chat), you answer the question directly and thoughtfully.
When asked to write or modify code, you explain the logic clearly and produce clean code.
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


_MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_ast_math(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_ast_math(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type in _MATH_OPERATORS:
            left = _eval_ast_math(node.left)
            right = _eval_ast_math(node.right)
            return _MATH_OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type in _MATH_OPERATORS:
            operand = _eval_ast_math(node.operand)
            return _MATH_OPERATORS[op_type](operand)
    raise ValueError("Not safe math")


def _try_solve_math(text: str) -> Optional[tuple[str, str]]:
    """Tries to extract and solve an arithmetic expression from user input."""
    t = text.lower()
    sqrt_match = re.search(r"(?:akar|sqrt|akar kuadrat dari)\s*(\d+(?:\.\d+)?)", t)
    if sqrt_match:
        val = float(sqrt_match.group(1))
        res = math.isqrt(int(val)) if val.is_integer() else round(math.sqrt(val), 4)
        return (f"√{sqrt_match.group(1)}", str(res))

    expr_match = re.search(r"(\d+(?:\.\d+)?(?:\s*[\+\-\*\/\^%]\s*\d+(?:\.\d+)?)+)", t)
    if expr_match:
        raw_expr = expr_match.group(1).strip()
        try:
            py_expr = raw_expr.replace("^", "**")
            parsed = ast.parse(py_expr, mode="eval")
            res_val = _eval_ast_math(parsed)
            if res_val.is_integer():
                formatted = str(int(res_val))
            else:
                formatted = f"{res_val:.4g}"
            return (raw_expr, formatted)
        except Exception:
            return None
    return None


class LLMClient:
    """Multi-provider LLM client supporting Gemini, OpenAI, DeepSeek, Claude, Groq, Ollama, and offline conversational fallback."""

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
            return {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview", "active": True}
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
            gemini_model = model or "gemini-3.1-flash-lite-preview"
            async for token in self._stream_openai_compatible(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key=self.gemini_key,
                model_name=gemini_model,
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

        # 5. Local Conversational & Knowledge Engine (Natural, flexible, never rigid!)
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
        """Intelligent, flexible conversational engine when no external API key is set."""
        p_clean = prompt.strip().lower()

        # 0. Math Calculations (safe arithmetic & square roots)
        math_res = _try_solve_math(p_clean)
        if math_res:
            expr, ans = math_res
            yield f"Hasil perhitungan dari **{expr}** adalah **{ans}**! 🧮\n\n"
            yield "Ada perhitungan matematika atau logika lain yang ingin saya bantu hitung?"
            return

        # 1. Indonesian Leaders & Key Public Figures
        if "prabowo" in p_clean:
            yield "### Prabowo Subianto\n\n"
            yield "**Jenderal TNI (Purn.) H. Prabowo Subianto Djojohadikusumo** adalah **Presiden Republik Indonesia ke-8** yang dilantik pada **20 Oktober 2024** bersama Wakil Presiden Gibran Rakabuming Raka.\n\n"
            yield "**Profil & Riwayat Singkat:**\n"
            yield "- **Jabatan Saat Ini:** Presiden Republik Indonesia (2024–2029).\n"
            yield "- **Jabatan Sebelumnya:** Menteri Pertahanan Republik Indonesia (2019–2024) pada masa Kabinet Indonesia Maju pimpinan Presiden Joko Widodo.\n"
            yield "- **Karier Militer:** Purnawirawan perwira tinggi TNI Angkatan Darat, pernah menjabat sebagai Komandan Jenderal Kopassus dan Panglima Kostrad.\n"
            yield "- **Politik:** Pendiri sekaligus Ketua Umum Partai Gerindra (Gerakan Indonesia Raya)."
            return

        if "jokowi" in p_clean or "joko widodo" in p_clean:
            yield "### Joko Widodo (Jokowi)\n\n"
            yield "**Ir. H. Joko Widodo** adalah **Presiden Republik Indonesia ke-7** yang menjabat selama dua periode dari **20 Oktober 2014 hingga 20 Oktober 2024**.\n\n"
            yield "Sebelum menjadi Presiden, ia pernah menjabat sebagai Wali Kota Surakarta (Solo) dan Gubernur DKI Jakarta. Masa kepemimpinannya dikenal luas dengan pembangunan infrastruktur masif (jalan tol trans-Jawa dan trans-Sumatera, bendungan, bandara) serta inisiasi pemindahan ibu kota negara ke Ibu Kota Nusantara (IKN)."
            return

        if "gibran" in p_clean:
            yield "### Gibran Rakabuming Raka\n\n"
            yield "**Gibran Rakabuming Raka** adalah **Wakil Presiden Republik Indonesia ke-14** yang dilantik pada 20 Oktober 2024 mendampingi Presiden Prabowo Subianto. Sebelumnya, ia menjabat sebagai Wali Kota Surakarta (2021–2024) dan merupakan putra sulung dari Presiden ke-7 RI Joko Widodo."
            return

        if "sby" in p_clean or "susilo bambang" in p_clean:
            yield "### Susilo Bambang Yudhoyono (SBY)\n\n"
            yield "**Jenderal TNI (Purn.) Prof. Dr. H. Susilo Bambang Yudhoyono** adalah **Presiden Republik Indonesia ke-6** yang menjabat selama dua periode (2004–2014). Beliau mencatat sejarah sebagai presiden Indonesia pertama yang terpilih melalui pemilihan umum secara langsung oleh rakyat pada pemilu 2004."
            return

        if "megawati" in p_clean:
            yield "### Megawati Soekarnoputri\n\n"
            yield "**Prof. Dr. (H.C.) Hj. Diah Permata Megawati Setiawati Soekarnoputri** adalah **Presiden Republik Indonesia ke-5** (2001–2004) dan presiden wanita pertama di Indonesia. Beliau adalah putri dari proklamator Soekarno dan saat ini menjabat sebagai Ketua Umum PDI Perjuangan."
            return

        if "gus dur" in p_clean or "abdurrahman wahid" in p_clean:
            yield "### KH. Abdurrahman Wahid (Gus Dur)\n\n"
            yield "**Dr. (H.C.) K.H. Abdurrahman Wahid** adalah **Presiden Republik Indonesia ke-4** (1999–2001). Beliau dikenal luas sebagai tokoh pluralisme, pembela hak-hak minoritas, ulama karismatik Nahdlatul Ulama (NU), serta bapak toleransi bangsa yang penuh dengan humor dan kebijaksanaan mendalam."
            return

        if "habibie" in p_clean:
            yield "### B.J. Habibie\n\n"
            yield "**Prof. Dr. Ing. H. Bacharuddin Jusuf Habibie** adalah **Presiden Republik Indonesia ke-3** (1998–1999). Beliau adalah ilmuwan dan teknokrat dirgantara jenius berkelas dunia yang memimpin transisi demokrasi reformasi Indonesia dan merancang pesawat kebanggaan Indonesia, N-250 Gatotkaca."
            return

        if "soeharto" in p_clean or "suharto" in p_clean:
            yield "### H.M. Soeharto\n\n"
            yield "**Jenderal Besar TNI (Purn.) H. M. Soeharto** adalah **Presiden Republik Indonesia ke-2** yang memimpin selama masa Orde Baru (1967–1998). Dikenal dengan julukan 'Bapak Pembangunan Nasional' karena fokus kepemimpinannya pada stabilitas ekonomi, swasembada pangan, dan Repelita."
            return

        if "soekarno" in p_clean or "bung karno" in p_clean:
            yield "### Ir. Soekarno (Bung Karno)\n\n"
            yield "**Dr. (H.C.) Ir. H. Soekarno** adalah **Proklamator Kemerdekaan dan Presiden Republik Indonesia pertama** (1945–1967). Bersama Mohammad Hatta, beliau memproklamasikan kemerdekaan Indonesia pada 17 Agustus 1945 dan mencetuskan konsep Pancasila sebagai dasar falsafah negara."
            return

        if "hatta" in p_clean or "bung hatta" in p_clean:
            yield "### Mohammad Hatta (Bung Hatta)\n\n"
            yield "**Dr. (H.C.) Drs. H. Mohammad Hatta** adalah **Proklamator Kemerdekaan dan Wakil Presiden Republik Indonesia pertama**. Beliau dikenal sebagai Bapak Koperasi Indonesia, pemikir ekonomi kerakyatan, pejuang diplomasi kemerdekaan, dan sosok teladan integritas tinggi."
            return

        # 2. Famous Tech & World Figures
        if "sam altman" in p_clean:
            yield "### Sam Altman\n\n"
            yield "**Samuel Harris Altman** adalah CEO dan salah satu pendiri **OpenAI**, organisasi riset AI terkemuka yang menciptakan **ChatGPT**, **GPT-4o**, dan **DALL-E**. Sebelumnya ia adalah presiden inkubator startup terkemuka dunia di Silicon Valley, Y Combinator."
            return

        if "elon musk" in p_clean:
            yield "### Elon Musk\n\n"
            yield "**Elon Reeve Musk** adalah pengusaha teknologi paling berpengaruh di dunia saat ini. Ia adalah CEO dan Chief Engineer di **SpaceX**, CEO di **Tesla**, pemilik platform sosial **X (Twitter)**, dan pendiri perusahaan AI **xAI (Grok)** serta **Neuralink**."
            return

        if "steve jobs" in p_clean:
            yield "### Steve Jobs\n\n"
            yield "**Steven Paul Jobs** (1955–2011) adalah pendiri legendaris dan mantan CEO **Apple Inc.** Bersama Steve Wozniak, ia merevolusi dunia komputasi personal, musik digital (iPod), telepon pintar (iPhone), dan animasi grafis komputer (Pixar)."
            return

        if "bill gates" in p_clean:
            yield "### Bill Gates\n\n"
            yield "**William Henry Gates III** adalah pendiri utama **Microsoft Corporation** yang mempopulerkan sistem operasi Windows. Saat ini ia mendedikasikan sebagian besar kekayaan dan waktunya untuk kegiatan filantropi global lewat Bill & Melinda Gates Foundation."
            return

        if "mark zuckerberg" in p_clean:
            yield "### Mark Zuckerberg\n\n"
            yield "**Mark Elliot Zuckerberg** adalah pendiri, chairman, dan CEO **Meta Platforms** (sebelumnya Facebook). Ia memimpin ekosistem media sosial terbesar dunia yang mencakup Facebook, Instagram, WhatsApp, serta inisiatif AI open-source (Llama)."
            return

        if "jensen huang" in p_clean:
            yield "### Jensen Huang\n\n"
            yield "**Jen-Hsun (Jensen) Huang** adalah co-founder, presiden, dan CEO **Nvidia Corporation**, raksasa semikonduktor yang memimpin revolusi komputasi GPU dan akselerator kecerdasan buatan (AI) di seluruh dunia saat ini."
            return

        if "linus torvalds" in p_clean:
            yield "### Linus Torvalds\n\n"
            yield "**Linus Benedict Torvalds** adalah insinyur perangkat lunak Finlandia-Amerika yang menciptakan kernel **Linux** (fondasi dari server cloud, Android, dan superkomputer dunia) serta sistem kontrol versi terdistribusi **Git**."
            return

        if "albert einstein" in p_clean or "einstein" in p_clean:
            yield "### Albert Einstein\n\n"
            yield "**Albert Einstein** (1879–1955) adalah fisikawan teoretis jenius peraih Nobel Fisika yang mencetuskan **Teori Relativitas Khusus dan Umum** serta persamaan massa-energi paling terkenal di dunia: **E = mc²**."
            return

        if "donald trump" in p_clean:
            yield "### Donald Trump\n\n"
            yield "**Donald John Trump** adalah politikus dan pengusaha asal Amerika Serikat yang menjabat sebagai Presiden AS ke-45 (2017–2021) dan kembali terpilih sebagai Presiden AS ke-47 setelah memenangkan Pemilihan Presiden AS 2024."
            return

        if "joe biden" in p_clean:
            yield "### Joe Biden\n\n"
            yield "**Joseph Robinette Biden Jr.** adalah politikus Amerika Serikat yang menjabat sebagai Presiden Amerika Serikat ke-46 (2021–2025). Sebelumnya ia adalah Wakil Presiden AS ke-47 di bawah Presiden Barack Obama."
            return

        # 3. Science & Nature
        if "langit biru" in p_clean or "kenapa langit" in p_clean or "mengapa langit" in p_clean:
            yield "### Mengapa Langit Berwarna Biru?\n\n"
            yield "Langit tampak biru karena fenomena fisika optik bernama **Hamburan Rayleigh (Rayleigh Scattering)**.\n\n"
            yield "1. Sinar matahari sebenarnya berwarna putih yang terdiri dari seluruh spektrum warna pelangi.\n"
            yield "2. Ketika sinar matahari memasuki atmosfer bumi, cahaya tersebut bertabrakan dengan molekul gas (oksigen dan nitrogen).\n"
            yield "3. Cahaya dengan panjang gelombang yang lebih pendek (seperti **biru** dan **ungu**) dihamburkan ke segala arah jauh lebih kuat daripada cahaya merah/kuning.\n"
            yield "4. Karena mata manusia jauh lebih sensitif terhadap warna biru dibandingkan ungu, kita melihat langit di siang hari berwarna biru cerah!"
            return

        if "fotosintesis" in p_clean:
            yield "### Apa Itu Fotosintesis?\n\n"
            yield "**Fotosintesis** adalah proses biokimia di mana tumbuhan hijau, alga, dan beberapa jenis bakteri memproduksi makanannya sendiri dengan memanfaatkan energi cahaya matahari.\n\n"
            yield "**Persamaan Kimia Utama:**\n"
            yield "`6CO₂ (Karbon Dioksida) + 6H₂O (Air) + Cahaya Matahari ➔ C₆H₁₂O₆ (Glukosa) + 6O₂ (Oksigen)`\n\n"
            yield "Proses ini berlangsung di dalam organel bernama **kloroplas** yang mengandung zat hijau daun (**klorofil**). Tanpa fotosintesis, bumi tidak akan memiliki suplai oksigen yang cukup untuk makhluk hidup!"
            return

        if "bumi bulat" in p_clean or "bumi datar" in p_clean or "bentuk bumi" in p_clean:
            yield "### Apakah Bumi Bulat atau Datar?\n\n"
            yield "Secara ilmiah dan empiris, **Bumi berbentuk bulat**—lebih tepatnya berbentuk **Geoid** atau *Oblate Spheroid* (sedikit pepat di kedua kutub dan menggelembung di bagian ekuator akibat gaya sentrifugal rotasi bumi).\n\n"
            yield "**Bukti Nyata yang Bisa Dibuktikan:**\n"
            yield "1. **Gerhana Bulan**: Bayangan bumi yang jatuh ke permukaan bulan selalu berbentuk lengkungan lingkaran.\n"
            yield "2. **Kapal di Laut**: Saat kapal berlayar menjauh ke horizon, lambung kapal menghilang lebih dulu sebelum tiang kapalnya.\n"
            yield "3. **Zona Waktu Berbeda**: Saat di Indonesia siang hari, di belahan bumi lain (seperti Amerika) adalah tengah malam.\n"
            yield "4. **Foto Satelit & Luar Angkasa**: Ribuan foto satelit dan astronaut dari ISS secara visual membuktikan kelengkungan bumi."
            return

        if "tata surya" in p_clean or "planet" in p_clean:
            yield "### Sistem Tata Surya Kita\n\n"
            yield "Tata Surya kita berpusat pada sebuah bintang yaitu **Matahari**, yang dikelilingi oleh **8 Planet Utama** berdasarkan urutan jaraknya:\n\n"
            yield "1. **Merkurius** - Planet terdekat dengan matahari, tanpa atmosfer tebal.\n"
            yield "2. **Venus** - Planet terpanas karena efek rumah kaca ekstrem.\n"
            yield "3. **Bumi** - Satu-satunya planet yang diketahui mendukung kehidupan.\n"
            yield "4. **Mars** - Planet merah dengan eksplorasi rover aktif.\n"
            yield "5. **Yupiter** - Planet gas raksasa terbesar dengan bintik merah raksasa.\n"
            yield "6. **Saturnus** - Terkenal dengan sistem cincin es dan batu yang spektakuler.\n"
            yield "7. **Uranus** - Planet es raksasa dengan sumbu rotasi miring ekstrem.\n"
            yield "8. **Neptunus** - Planet terjauh dan terdingin dengan angin supersonik."
            return

        if "gravitasi" in p_clean or "gravity" in p_clean:
            yield "### Apa Itu Gravitasi?\n\n"
            yield "**Gravitasi** adalah gaya tarik universal alami yang terjadi antara semua materi yang memiliki massa di alam semesta.\n\n"
            yield "- **Pandangan Newton**: Gravitasi adalah gaya tarik-menarik antara dua massa yang sebanding dengan perkalian massa keduanya dan berbanding terbalik dengan kuadrat jaraknya (`F = G * (m1*m2)/r²`).\n"
            yield "- **Pandangan Einstein (Relativitas Umum)**: Gravitasi bukanlah sekadar 'tarikan tak terlihat', melainkan akibat dari kelengkungan ruang-waktu (*space-time curvature*) yang disebabkan oleh massa benda yang sangat besar (seperti matahari dan bumi)."
            return

        if any(w in p_clean for w in ["apa itu ai", "kecerdasan buatan", "machine learning", "deep learning"]):
            yield "### Apa Itu Kecerdasan Buatan (AI)?\n\n"
            yield "**Kecerdasan Buatan (Artificial Intelligence / AI)** adalah bidang ilmu komputer yang bertujuan menciptakan sistem yang mampu melakukan tugas-tugas yang biasanya membutuhkan kecerdasan manusia—seperti menalar, memahami bahasa, mengenali gambar, dan mengambil keputusan.\n\n"
            yield "### Tingkatan Teknologi AI:\n"
            yield "1. **Machine Learning (ML)**: Algoritma yang belajar mengenali pola dari data masa lalu tanpa harus diprogram secara kaku.\n"
            yield "2. **Deep Learning (DL)**: Menggunakan jaringan saraf tiruan berlapis (*deep neural networks*) yang terinspirasi dari otak manusia.\n"
            yield "3. **Large Language Models (LLM)**: Model AI seperti GPT-4, Claude, dan Gemini yang dilatih pada triliunan token teks untuk memahami dan menghasilkan bahasa alami."
            return

        # 4. Indonesian Food, Daily Life & Self-Care
        if "nasi goreng" in p_clean:
            yield "### Resep Rahasia Nasi Goreng Spesial Lezat 🍳\n\n"
            yield "**Kunci Utama:** Gunakan nasi pera atau nasi dingin yang sudah disimpan di kulkas semalaman (agar tidak lembek saat diaduk di wajan).\n\n"
            yield "**Bumbu Halus:**\n"
            yield "- 4 butir bawang merah & 2 siung bawang putih\n"
            yield "- 3 buah cabai rawit (sesuai selera pedas)\n"
            yield "- 1/2 sdt terasi bakar (opsional tapi bikin gurih harum)\n"
            yield "- Garam, merica, dan kaldu jamur secukupnya\n\n"
            yield "**Cara Masak Cepat:**\n"
            yield "1. Panaskan minyak di wajan dengan api besar (*wok heat*).\n"
            yield "2. Orak-arik 1 butir telur sampai harum, lalu masukkan bumbu halus dan tumis sampai wangi matang.\n"
            yield "3. Masukkan nasi dingin, beri kecap manis dan sedikit kecap asin di pinggir wajan agar ada aroma karamel asap (*wok hei*).\n"
            yield "4. Aduk cepat merata selama 2-3 menit dengan api besar. Sajikan selagi hangat dengan taburan bawang goreng dan kerupuk!"
            return

        if "rendang" in p_clean:
            yield "### Rendang Daging Khas Minangkabau 🍛\n\n"
            yield "**Rendang** adalah salah satu hidangan terenak di dunia versi CNN Travel. Filosofi rendang Minang mengandalkan kesabaran memasak perlahan (*slow cooking*) menggunakan santan murni kental dan aneka rempah (lengkuas, serai, jahe, daun kunyit, daun jeruk, dan cabai merah giling).\n\n"
            yield "**Tiga Tahapan Rendang:**\n"
            yield "1. **Gulai**: Kuah masih encer berwarna kuning kemerahan.\n"
            yield "2. **Kalio**: Santan mulai mengental, berminyak, dan berwarna cokelat muda.\n"
            yield "3. **Rendang Sejati**: Minyak terserap habis, bumbu berubah warna menjadi cokelat gelap kehitaman yang kering dan tahan berminggu-minggu tanpa bahan pengawet!"
            return

        if "kopi" in p_clean or "buat kopi" in p_clean:
            yield "### Tips Menyeduh Kopi Enak Ala Barista ☕\n\n"
            yield "1. **Rasio Kopi ke Air**: Gunakan rasio emas **1:15** atau **1:16** (contoh: 15 gram bubuk kopi untuk 225-240 ml air).\n"
            yield "2. **Suhu Air**: Jangan gunakan air mendidih 100°C karena akan membakar kopi dan membuatnya pahit sepat. Suhu ideal adalah **90°C – 94°C** (diamkan air mendidih sekitar 45 detik sebelum dituang).\n"
            yield "3. **Blooming**: Tuang 30-40 ml air panas pertama dan diamkan selama 30-45 detik agar gas CO₂ dari kopi keluar dengan sempurna sebelum seduhan utama."
            return

        if any(w in p_clean for w in ["tips belajar", "tips produktif", "pomodoro"]):
            yield "### Tips Belajar & Produktivitas Maksimal 🎯\n\n"
            yield "1. **Teknik Pomodoro**: Fokus belajar/coding penuh selama 25 menit (tanpa notifikasi HP), lalu istirahat santai 5 menit. Setelah 4 sesi, ambil istirahat panjang 15-30 menit.\n"
            yield "2. **Feynman Technique**: Jelaskan konsep yang sedang kamu pelajari kepada orang awam atau bayangkan kamu mengajar anak kecil dengan kata-kata sederhana. Jika ada bagian yang bingung, di situlah letak gap pemahamanmu.\n"
            yield "3. **Active Recall & Spaced Repetition**: Jangan hanya membaca ulang buku/kode, tapi uji dirimu sendiri dengan membuat catatan kuis dan ulangi dalam interval beberapa hari."
            return

        if any(w in p_clean for w in ["motivasi", "semangat", "capek", "lelah", "menyerah"]):
            yield "### Pengingat Untukmu Hari Ini ✨\n\n"
            yield "*'Setiap langkah kecil yang kamu ambil hari ini, betapapun lambatnya terasa, sedang membangun pondasi kesuksesan besar di masa depan.'*\n\n"
            yield "Merasa lelah itu manusiawi, tapi jangan pernah menyerah. Luangkan waktu sejenak untuk tarik napas dalam-dalam, minum air putih, dan istirahatkan pikiran. Studio ini dan saya siap mendukungmu kembali kapan saja kamu siap melangkah lagi! 💪🚀"
            return

        # 5. Humor, Jokes & Fun
        if any(w in p_clean for w in ["lelucon", "jokes", "lucu", "tebak-tebakan", "cerita lucu"]):
            yield "### Ini Tebak-Tebakan Santai Buatmu! 😄\n\n"
            yield "**Tanya:** *Kenapa programmer suka pakai kacamata hitam di malam hari?*\n\n"
            yield "**Jawab:** *Karena kode yang mereka tulis terlalu terang benderang masa depannya!* 😎💻\n\n"
            yield "---\n"
            yield "**Satu lagi:**\n"
            yield "**Tanya:** *Sayur apa yang jago bela diri?*\n"
            yield "**Jawab:** *Brokoli Lee!* 🥦🥋"
            return

        if any(w in p_clean for w in ["pantun", "gombal"]):
            yield "### Pantun Spesial Buatmu! 🌸\n\n"
            yield "*Jalan-jalan ke kota Blitar,*\n"
            yield "*Jangan lupa beli sukun.*\n"
            yield "*Kalau ingin jadi programmer pintar,*\n"
            yield "*Belajar dan coding-lah dengan tekun!* 🚀✨"
            return

        # 6. Greetings & Social Chat
        if any(w in p_clean for w in ["hallo", "halo", "hai", "hi", "hey", "hei", "pagi", "siang", "sore", "malam", "assalamualaikum"]):
            yield "Halo Iqbal! 👋 Senang bertemu denganmu.\n\n"
            yield "Saya **ADITH AI**, asisten coding dan partner berpikir pribadimu di studio ini. "
            yield "Ada yang bisa saya bantu hari ini? Kamu bisa menyuruh saya menulis kode, refactor fungsi, menjawab pertanyaan seputar sains, sejarah, tokoh dunia, matematika, atau sekadar ngobrol santai!"
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
            yield "4. **General Conversation**: Menjawab segala pertanyaan dari obrolan santai, sejarah, tokoh dunia, matematika, hingga tugas coding rumit."
            return

        if any(w in p_clean for w in ["terima kasih", "makasih", "thanks", "thank you"]):
            yield "Sama-sama, Iqbal! Senang bisa membantumu. Jika butuh bantuan lain atau mau nambah fitur baru, langsung panggil saya lagi ya! 😊"
            return

        # 7. Software Engineering & Architecture
        if "microservice" in p_clean or "microservices" in p_clean:
            yield "### Apa Itu Arsitektur Microservices?\n\n"
            yield "**Microservices** adalah pola arsitektur di mana aplikasi besar dipecah menjadi kumpulan layanan-layanan kecil yang mandiri (*decoupled*), masing-masing menjalankan proses bisnis spesifik dan berkomunikasi melalui protokol jaringan ringan (seperti HTTP REST, gRPC, atau Message Broker seperti Kafka/NATS).\n\n"
            yield "**Kelebihan Utama:**\n"
            yield "- **Scalability Mandiri**: Layanan yang tinggi trafik (misal: Checkout) bisa di-scale terpisah tanpa perlu memperbesar seluruh aplikasi.\n"
            yield "- **Polyglot**: Tim bisa memakai bahasa berbeda untuk layanan berbeda (seperti ADITH AI Studio: Go untuk Gateway, Python untuk AI Engine, TypeScript untuk Frontend).\n"
            yield "- **Fault Isolation**: Jika satu service error, sistem utama tidak langsung mati total."
            return

        if "docker" in p_clean or "container" in p_clean:
            yield "### Apa Itu Docker & Mengapa Sangat Populer?\n\n"
            yield "**Docker** adalah platform kontainerisasi yang membungkus aplikasi beserta seluruh dependensinya (library, konfigurasi runtime, dan binary) ke dalam satu wadah terisolasi bernama **Container**.\n\n"
            yield "**Prinsip Utama:** *'Build Once, Run Anywhere'*. Menghilangkan masalah klasik *'di laptop saya jalan, tapi di server kok error'*. Di ADITH AI Studio, kita sudah siapkan arsitektur Dockerfile multi-stage agar nanti bisa di-deploy ke server cloud dengan mudah!"
            return

        if "kubernetes" in p_clean or "k8s" in p_clean:
            yield "### Apa Itu Kubernetes (K8s)?\n\n"
            yield "**Kubernetes (K8s)** adalah platform open-source orkestrasi kontainer yang awalnya dikembangkan oleh Google. Fungsinya adalah mengotomatisasi deployment, scaling, load balancing, dan manajemen ratusan hingga ribuan kontainer Docker di cluster server."
            return

        if "rest api" in p_clean or "apa itu api" in p_clean:
            yield "### Apa Itu REST API?\n\n"
            yield "**REST (Representational State Transfer) API** adalah standar antarmuka komunikasi antar aplikasi menggunakan protokol HTTP standar.\n\n"
            yield "- **GET**: Mengambil data resource (contoh: `GET /users`).\n"
            yield "- **POST**: Membuat data baru (contoh: `POST /users`).\n"
            yield "- **PUT / PATCH**: Memperbarui data yang ada.\n"
            yield "- **DELETE**: Menghapus data.\n"
            yield "Data yang dikirim dan diterima biasanya diformat dalam bentuk **JSON**."
            return

        if "sql" in p_clean or "nosql" in p_clean or "database" in p_clean:
            yield "### SQL vs NoSQL: Kapan Harus Memilih yang Mana?\n\n"
            yield "- **SQL (Relational DB, contoh: PostgreSQL, MySQL)**: Menggunakan tabel bertipe data ketat (*strict schema*), mendukung transaksi ACID penuh. Sangat cocok untuk data finansial, e-commerce, dan sistem yang membutuhkan konsistensi tinggi.\n"
            yield "- **NoSQL (Non-Relational, contoh: MongoDB, Redis, Qdrant)**: Skema fleksibel tanpa relasi tabel kaku (*document, key-value, vector*). Sangat cocok untuk high-throughput data, caching cepat, atau pencarian kemiripan AI (seperti Qdrant di studio ini)."
            return

        if "git" in p_clean or "github" in p_clean:
            yield "### Dasar Penggunaan Git & GitHub\n\n"
            yield "**Git** adalah sistem kontrol versi untuk mencatat riwayat perubahan file kode, sedangkan **GitHub** adalah platform hosting cloud untuk menyimpan repositori Git tersebut.\n\n"
            yield "**Perintah Esensial:**\n"
            yield "- `git status`: Melihat file mana yang diubah atau belum di-commit.\n"
            yield "- `git add .`: Memasukkan semua perubahan ke staging area.\n"
            yield "- `git commit -m \"pesan commit\"`: Menyimpan rekaman perubahan dengan pesan jelas.\n"
            yield "- `git push origin main`: Mengirim commit lokal ke repositori remote di GitHub."
            return

        # 8. Natural Open-Ended Conversation (Not rigid, no unsolicited coding questions!)
        yield f"Mengenai **\"{prompt.strip()}\"**:\n\n"
        yield "Pertanyaan yang menarik! Saat ini saya beroperasi menggunakan mesin percakapan lokal internal **ADITH AI**.\n\n"
        yield "Sebagai asisten pribadimu, saya selalu siap mendiskusikan topik apa pun—mulai dari ide proyek, logika pemrograman, strategi arsitektur sistem, hingga tanya jawab santai!\n\n"
        if context_snippets:
            yield f"💡 *Konteks Codebase Terkait di Workspace:*\n{context_snippets[:300]}...\n\n"

        yield "Kamu bisa menanyakan lebih detail bagian mana yang ingin kita bahas, atau kita bisa langsung mulai mengerjakan sesuatu di studio ini! 🚀\n\n"
        yield "---\n"
        yield "💡 **Tips:** Untuk membuka kemampuan menjawab jutaan data internet real-time tanpa batas (seperti ChatGPT / Gemini asli), kamu bisa memasukkan **Gemini API Key (GRATIS)** di file `.env` studio ini (`GEMINI_API_KEY=...`)."


_DEFAULT_CLIENT: Optional[LLMClient] = None


def get_default_llm_client() -> LLMClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = LLMClient()
    return _DEFAULT_CLIENT
