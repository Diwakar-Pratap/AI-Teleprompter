import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    backend_host: str = "127.0.0.1"
    backend_port: int = 8765
    claude_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    hf_token: Optional[str] = None
    deepgram_api_key: Optional[str] = None
    google_speech_api_key: Optional[str] = None
    stt_provider: str = "google"
    stt_language: str = "en-IN"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
