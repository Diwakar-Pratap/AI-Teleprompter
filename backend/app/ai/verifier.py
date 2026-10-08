"""
API Connection Tester.
Verifies whether user-provided API keys (Claude, OpenAI, Gemini) are valid and working.
"""

import time
from typing import Dict, Any, Optional
import httpx

from app.logging.logger import get_logger

logger = get_logger(__name__)


async def test_api_connection(provider: str, api_key: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Test live connectivity with the specified AI provider.
    Returns:
    {
        "success": bool,
        "provider": str,
        "latency_ms": int,
        "message": str,
        "details": Optional[str]
    }
    """
    prov = provider.lower().strip()
    key = (api_key or "").strip()
    if not key:
        from app.settings.config import settings
        import os
        if prov in ("nvidia", "deepseek"):
            key = settings.nvidia_api_key or os.getenv("NVIDIA_API_KEY") or ""
        elif prov in ("huggingface", "hf"):
            key = settings.hf_token or os.getenv("HF_TOKEN") or ""
        elif prov in ("claude", "anthropic"):
            key = settings.claude_api_key or os.getenv("CLAUDE_API_KEY") or ""
        elif prov == "openai":
            key = settings.openai_api_key or os.getenv("OPENAI_API_KEY") or ""
        elif prov in ("gemini", "google"):
            key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or ""

    if not key:
        return {
            "success": False,
            "provider": prov,
            "latency_ms": 0,
            "message": "API key cannot be empty and none is currently saved.",
            "details": None,
        }

    start_time = time.perf_counter()

    try:
        if prov in ("claude", "anthropic"):
            # Anthropic Claude test
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            body = {
                "model": model or "claude-3-5-sonnet-20241022",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "ping"}],
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=body)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return {
                        "success": True,
                        "provider": "claude",
                        "latency_ms": latency,
                        "message": f"Anthropic Claude API connected successfully! ({latency}ms)",
                        "details": "Model responded to ping.",
                    }
                else:
                    err_json = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error", {}).get("message") or f"HTTP {res.status_code}: {res.text[:200]}"
                    return {
                        "success": False,
                        "provider": "claude",
                        "latency_ms": latency,
                        "message": f"Anthropic Claude connection failed ({res.status_code})",
                        "details": err_msg,
                    }

        elif prov == "openai":
            # OpenAI test
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": model or "gpt-4o-mini",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=body)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return {
                        "success": True,
                        "provider": "openai",
                        "latency_ms": latency,
                        "message": f"OpenAI API connected successfully! ({latency}ms)",
                        "details": "Model responded to ping.",
                    }
                else:
                    err_json = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error", {}).get("message") or f"HTTP {res.status_code}: {res.text[:200]}"
                    return {
                        "success": False,
                        "provider": "openai",
                        "latency_ms": latency,
                        "message": f"OpenAI connection failed ({res.status_code})",
                        "details": err_msg,
                    }

        elif prov in ("gemini", "google"):
            # Google Gemini test
            gemini_model = model or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={key}"
            headers = {"Content-Type": "application/json"}
            body = {
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 5},
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=body)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return {
                        "success": True,
                        "provider": "gemini",
                        "latency_ms": latency,
                        "message": f"Google Gemini API connected successfully! ({latency}ms)",
                        "details": "Model responded to ping.",
                    }
                else:
                    err_json = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error", {}).get("message") or f"HTTP {res.status_code}: {res.text[:200]}"
                    return {
                        "success": False,
                        "provider": "gemini",
                        "latency_ms": latency,
                        "message": f"Google Gemini connection failed ({res.status_code})",
                        "details": err_msg,
                    }

        elif prov in ("nvidia", "deepseek"):
            # NVIDIA API test (https://integrate.api.nvidia.com/v1)
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            target_model = model if model and "deepseek-v4.1" not in model else "meta/llama-3.2-11b-vision-instruct"
            body = {
                "model": target_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 10,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=body)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return {
                        "success": True,
                        "provider": "nvidia",
                        "latency_ms": latency,
                        "message": f"NVIDIA API connected successfully! ({latency}ms)",
                        "details": f"Model {target_model} responded to ping.",
                    }
                else:
                    err_json = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error", {}).get("message") or f"HTTP {res.status_code}: {res.text[:200]}"
                    return {
                        "success": False,
                        "provider": "nvidia",
                        "latency_ms": latency,
                        "message": f"NVIDIA API connection failed ({res.status_code})",
                        "details": err_msg,
                    }

        elif prov in ("huggingface", "hf"):
            # Hugging Face Router test (deepseek-ai/DeepSeek-R1:fastest)
            hf_model = model or "deepseek-ai/DeepSeek-R1:fastest"
            url = "https://router.huggingface.co/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": hf_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 10,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=body)
                latency = int((time.perf_counter() - start_time) * 1000)

                if res.status_code == 200:
                    return {
                        "success": True,
                        "provider": "huggingface",
                        "latency_ms": latency,
                        "message": f"Hugging Face API connected successfully! ({latency}ms)",
                        "details": f"Model {hf_model} responded.",
                    }
                else:
                    err_json = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_json.get("error")
                    if isinstance(err_msg, dict):
                        err_msg = err_msg.get("message")
                    if not err_msg:
                        err_msg = f"HTTP {res.status_code}: {res.text[:200]}"
                    return {
                        "success": False,
                        "provider": "huggingface",
                        "latency_ms": latency,
                        "message": f"Hugging Face connection failed ({res.status_code})",
                        "details": str(err_msg),
                    }

        else:
            return {
                "success": False,
                "provider": prov,
                "latency_ms": 0,
                "message": f"Unsupported provider: {provider}",
                "details": "Supported providers: claude, openai, gemini, nvidia, huggingface",
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "provider": prov,
            "latency_ms": int((time.perf_counter() - start_time) * 1000),
            "message": "Connection timed out (10s). Check your internet connection.",
            "details": "Request timed out.",
        }
    except Exception as e:
        return {
            "success": False,
            "provider": prov,
            "latency_ms": int((time.perf_counter() - start_time) * 1000),
            "message": f"Network/Connection error: {str(e)}",
            "details": str(e),
        }
