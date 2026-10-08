"""
AI Chat Engine: Provides interactive chat and live teleprompter response generation.
Supports multi-provider streaming:
- Anthropic Claude (claude-3-5-sonnet)
- OpenAI (gpt-4o, gpt-4o-mini)
- Google Gemini (gemini-1.5-flash, gemini-1.5-pro)
- Augmented with personal details & documents via SQLite FTS5 KnowledgeStore (RAG)
- Fallback local intelligent generator when no API key is set
"""

import os
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx

from app.settings.config import settings
from app.knowledge.store import KnowledgeStore
from app.logging.logger import get_logger

logger = get_logger(__name__)


def _read_env_file_key(var_name: str) -> Optional[str]:
    """Read a key directly from .env files on disk as a reliable fallback."""
    candidate_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"),
        ".env",
        "backend/.env",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"{var_name}=") and not line.startswith("#"):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val and not val.startswith("your_"):
                                return val
            except Exception:
                pass
    return None


class ChatEngine:
    """Manages conversational dialogue, RAG knowledge retrieval, and streaming responses."""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None):
        self.api_key = api_key
        self.provider = provider

    def _resolve_credentials(self) -> tuple[str, Optional[str]]:
        """Resolve active AI provider and API key from settings or environment."""
        try:
            from app.api.routes import _settings
            route_prov = getattr(_settings.ai, "provider", None)
        except Exception:
            route_prov = None

        prov = (self.provider or route_prov or os.getenv("AI_PROVIDER") or _read_env_file_key("AI_PROVIDER") or "nvidia").lower()
        key = self.api_key

        if not key:
            if prov in ("claude", "anthropic"):
                key = settings.claude_api_key or os.getenv("CLAUDE_API_KEY") or _read_env_file_key("CLAUDE_API_KEY")
            elif prov == "openai":
                key = settings.openai_api_key or os.getenv("OPENAI_API_KEY") or _read_env_file_key("OPENAI_API_KEY")
            elif prov in ("gemini", "google"):
                key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or _read_env_file_key("GEMINI_API_KEY")
            elif prov in ("nvidia", "deepseek"):
                key = settings.nvidia_api_key or os.getenv("NVIDIA_API_KEY") or _read_env_file_key("NVIDIA_API_KEY")
            elif prov in ("huggingface", "hf"):
                key = settings.hf_token or os.getenv("HF_TOKEN") or _read_env_file_key("HF_TOKEN")

        return prov, key

    async def stream_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream assistant response tokens with Knowledge Base context augmentation."""
        prov, key = self._resolve_credentials()

        # 1. RAG Knowledge Base Retrieval
        knowledge_context = ""
        try:
            store = KnowledgeStore.get_instance()
            relevant_chunks = store.search(prompt, limit=3)
            if relevant_chunks:
                context_lines = []
                for chunk in relevant_chunks:
                    title = chunk.get("title", "Document")
                    text = chunk.get("content_chunk", "")
                    context_lines.append(f"[{title}]:\n{text.strip()}")
                knowledge_context = "\n\nRelevant Personal Knowledge Base / Details:\n" + "\n---\n".join(context_lines)
                logger.info("Retrieved knowledge chunks for prompt", count=len(relevant_chunks))
        except Exception as e:
            logger.warning("Knowledge search error during chat generation", error=str(e))

        base_sys_prompt = system_prompt or (
            "You are AI Teleprompter Assistant — an intelligent, concise, and helpful desktop AI co-pilot. "
            "Give direct, high-value, crisp answers suitable for quick reading. "
            "If personal knowledge base details or resume context are provided, use them accurately to answer from the user's perspective."
        )

        sys_prompt = f"{base_sys_prompt}\n{knowledge_context}".strip() if knowledge_context else base_sys_prompt

        messages = []
        if history:
            for item in history[-10:]:
                role = "user" if item.get("role") == "user" else "assistant"
                content = item.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        # 2. Call active API provider if valid key exists (bypass during unit tests)
        if key and not key.startswith("your_") and os.getenv("TESTING") != "1":
            try:
                # ── Claude (Anthropic) ──────────────────────────
                if prov in ("claude", "anthropic"):
                    headers = {
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    }
                    body = {
                        "model": "claude-3-5-sonnet-20241022",
                        "max_tokens": 1024,
                        "system": sys_prompt,
                        "messages": messages,
                        "stream": True,
                    }
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream(
                            "POST", "https://api.anthropic.com/v1/messages", headers=headers, json=body
                        ) as response:
                            if response.status_code == 200:
                                async for line in response.aiter_lines():
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            data = json.loads(data_str)
                                            if data.get("type") == "content_block_delta":
                                                delta = data.get("delta", {})
                                                if delta.get("type") == "text_delta":
                                                    yield delta.get("text", "")
                                        except Exception:
                                            continue
                                return
                            else:
                                err_body = await response.aread()
                                logger.warning("Claude API error", code=response.status_code, body=err_body.decode(errors="ignore"))

                # ── OpenAI ──────────────────────────────────────
                elif prov == "openai":
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    oai_messages = [{"role": "system", "content": sys_prompt}] + messages
                    body = {
                        "model": "gpt-4o-mini",
                        "messages": oai_messages,
                        "stream": True,
                        "max_tokens": 1024,
                    }
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream(
                            "POST", "https://api.openai.com/v1/chat/completions", headers=headers, json=body
                        ) as response:
                            if response.status_code == 200:
                                async for line in response.aiter_lines():
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            data = json.loads(data_str)
                                            choices = data.get("choices", [])
                                            if choices:
                                                delta = choices[0].get("delta", {})
                                                content = delta.get("content", "")
                                                if content:
                                                    yield content
                                        except Exception:
                                            continue
                                return
                            else:
                                err_body = await response.aread()
                                logger.warning("OpenAI API error", code=response.status_code, body=err_body.decode(errors="ignore"))

                # ── Google Gemini ───────────────────────────────
                elif prov in ("gemini", "google"):
                    gemini_model = os.getenv("AI_MODEL") or "gemini-1.5-flash"
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:streamGenerateContent?alt=sse&key={key}"
                    headers = {"Content-Type": "application/json"}
                    gemini_contents = []
                    for m in messages:
                        r = "user" if m["role"] == "user" else "model"
                        gemini_contents.append({"role": r, "parts": [{"text": m["content"]}]})

                    body = {
                        "system_instruction": {"parts": [{"text": sys_prompt}]},
                        "contents": gemini_contents,
                        "generationConfig": {"maxOutputTokens": 1024},
                    }
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream("POST", url, headers=headers, json=body) as response:
                            if response.status_code == 200:
                                async for line in response.aiter_lines():
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        try:
                                            data = json.loads(data_str)
                                            candidates = data.get("candidates", [])
                                            if candidates:
                                                parts = candidates[0].get("content", {}).get("parts", [])
                                                for p in parts:
                                                    t = p.get("text", "")
                                                    if t:
                                                        yield t
                                        except Exception:
                                            continue
                                return
                            else:
                                err_body = await response.aread()
                                logger.warning("Gemini API error", code=response.status_code, body=err_body.decode(errors="ignore"))

                # ── NVIDIA / DeepSeek ───────────────────────────
                elif prov in ("nvidia", "deepseek"):
                    m = os.getenv("AI_MODEL")
                    nvidia_model = m if m and "deepseek-v4.1" not in m else "meta/llama-3.2-11b-vision-instruct"
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    nv_messages = [{"role": "system", "content": sys_prompt}] + messages
                    body = {
                        "model": nvidia_model,
                        "messages": nv_messages,
                        "stream": True,
                        "max_tokens": 1024,
                    }
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream(
                            "POST", "https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=body
                        ) as response:
                            if response.status_code == 200:
                                async for line in response.aiter_lines():
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            data = json.loads(data_str)
                                            choices = data.get("choices", [])
                                            if choices:
                                                delta = choices[0].get("delta", {})
                                                content = delta.get("content", "")
                                                if content:
                                                    yield content
                                        except Exception:
                                            continue
                                return
                            else:
                                err_body = await response.aread()
                                err_msg = err_body.decode(errors="ignore")
                                logger.warning("NVIDIA API error", code=response.status_code, body=err_msg)
                                yield f"⚠️ NVIDIA API error ({response.status_code}): {err_msg[:200]}"
                                return

                # ── Hugging Face Router (DeepSeek-R1, etc.) ───────
                elif prov in ("huggingface", "hf"):
                    hf_model = os.getenv("AI_MODEL") or "deepseek-ai/DeepSeek-R1:fastest"
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    hf_messages = [{"role": "system", "content": sys_prompt}] + messages
                    body = {
                        "model": hf_model,
                        "messages": hf_messages,
                        "stream": True,
                        "max_tokens": 1024,
                    }
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        async with client.stream(
                            "POST", "https://router.huggingface.co/v1/chat/completions", headers=headers, json=body
                        ) as response:
                            if response.status_code == 200:
                                async for line in response.aiter_lines():
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            data = json.loads(data_str)
                                            choices = data.get("choices", [])
                                            if choices:
                                                delta = choices[0].get("delta", {})
                                                content = delta.get("content", "")
                                                if content:
                                                    yield content
                                        except Exception:
                                            continue
                                return
                            else:
                                err_body = await response.aread()
                                err_msg = err_body.decode(errors="ignore")
                                logger.warning("Hugging Face API error", code=response.status_code, body=err_msg)
                                yield f"⚠️ Hugging Face API error ({response.status_code}): {err_msg[:200]}"
                                return

            except Exception as e:
                logger.warning("Cloud streaming failed", provider=prov, error=str(e))
                yield f"⚠️ Error calling {prov.upper()}: {str(e)}"
                return

        # 3. Local fallback response generator (only when no API key is provided)
        simulated_response = self._generate_local_reply(prompt, knowledge_context)
        words = simulated_response.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.035)

    def _generate_local_reply(self, prompt: str, knowledge_context: str = "") -> str:
        """Local response generator with knowledge base context awareness."""
        p_lower = prompt.lower()

        if knowledge_context:
            return (
                f"Based on your Knowledge Base details: {knowledge_context[:260]}... "
                f"\n\nHere is a tailored answer: To address \"{prompt}\", highlight your documented experience with these tools and results."
            )
        elif "hello" in p_lower or "hi" in p_lower:
            return "Hello! I am your AI Teleprompter assistant. I can help answer questions, summarize notes, review interview topics, or explain technical concepts."
        elif "interview" in p_lower:
            return "For interviews, focus on the STAR method (Situation, Task, Action, Result) for behavioral questions, and explain your trade-offs clearly for system design and architecture questions."
        elif "system design" in p_lower:
            return "When approaching system design: 1. Clarify functional and non-functional requirements (scalability, latency, availability). 2. Define high-level API & data models. 3. Diagram the architecture (load balancer, services, caching, database partitioning). 4. Address bottlenecks and failure modes."
        elif "help" in p_lower:
            return "You can use this chat to practice interview questions, query your personal context, brainstorm answers, or request concise explanations. Toggle back to the Prompter tab to monitor live interview audio."
        else:
            return (
                f"I received your question: \"{prompt}\". "
                "You can configure your Claude, OpenAI, or Gemini API Key in the Settings menu (⚙️) to get live AI responses. "
                "You can also upload your resume/PDF in the Knowledge Base tab so I can answer questions using your exact details!"
            )

