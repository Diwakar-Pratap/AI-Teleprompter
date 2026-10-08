import os
import json
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

CONFIG_DIR = Path.home() / ".ai-teleprompter"
CONFIG_FILE = CONFIG_DIR / "config.json"
SUT_ENV_FILE = CONFIG_DIR / ".env"


def _load_sut_config() -> dict:
    data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except Exception:
            pass
    if SUT_ENV_FILE.exists():
        try:
            with open(SUT_ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        data[k.strip().lower()] = v.strip()
                        os.environ[k.strip()] = v.strip()
        except Exception:
            pass
    return data


sut_config = _load_sut_config()


class Settings(BaseSettings):
    backend_host: str = "127.0.0.1"
    backend_port: int = 8765
    claude_api_key: Optional[str] = sut_config.get("claude_api_key") or os.getenv("CLAUDE_API_KEY")
    openai_api_key: Optional[str] = sut_config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    gemini_api_key: Optional[str] = sut_config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY")
    nvidia_api_key: Optional[str] = sut_config.get("nvidia_api_key") or os.getenv("NVIDIA_API_KEY")
    hf_token: Optional[str] = sut_config.get("hf_token") or os.getenv("HF_TOKEN")
    deepgram_api_key: Optional[str] = sut_config.get("deepgram_api_key") or os.getenv("DEEPGRAM_API_KEY")
    google_speech_api_key: Optional[str] = sut_config.get("google_speech_api_key") or os.getenv("GOOGLE_SPEECH_API_KEY")
    stt_provider: str = sut_config.get("stt_provider") or "google"
    stt_language: str = sut_config.get("stt_language") or "en-IN"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

