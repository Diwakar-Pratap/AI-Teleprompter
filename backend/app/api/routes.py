"""
API routes — Health, Settings, Sessions, Audio device management.
"""

import os
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from pydantic import BaseModel

from app.audio.devices import AudioDeviceManager
from app.audio.types import AudioSourceType
from app.logging.logger import get_logger

logger = get_logger(__name__)
api_router = APIRouter()


# ─── Root ─────────────────────────────────────────────────────────────────────

@api_router.get("/")
async def root() -> dict[str, str]:
    """Root info endpoint."""
    return {
        "app": "AI Teleprompter API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "ws": "/ws/events",
    }


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    components: dict[str, str]


@api_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        components={
            "database": "ok",
            "audio": "ready",
            "stt": "google_speech",
            "ai": "ready",
        },
    )


# ─── Audio Devices ────────────────────────────────────────────────────────────

class AudioDeviceResponse(BaseModel):
    id: int
    name: str
    hostapi: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_default_input: bool
    is_default_output: bool
    is_loopback: bool


@api_router.get("/audio/devices", response_model=List[AudioDeviceResponse])
async def list_audio_devices() -> List[AudioDeviceResponse]:
    """List available audio capture and playback devices."""
    devices = AudioDeviceManager.get_devices()
    return [
        AudioDeviceResponse(
            id=d.id,
            name=d.name,
            hostapi=d.hostapi,
            max_input_channels=d.max_input_channels,
            max_output_channels=d.max_output_channels,
            default_samplerate=d.default_samplerate,
            is_default_input=d.is_default_input,
            is_default_output=d.is_default_output,
            is_loopback=d.is_loopback,
        )
        for d in devices
    ]


# ─── Settings ─────────────────────────────────────────────────────────────────

class GeneralSettings(BaseModel):
    start_with_os: bool = False
    start_minimized: bool = False
    default_mode: str = "interview"
    auto_start_listening: bool = False


class AudioSettings(BaseModel):
    source: str = "system"
    device_id: Optional[int] = None
    vad_enabled: bool = True
    vad_sensitivity: float = 0.5
    stt_provider: str = os.getenv("STT_PROVIDER", "google")


class AISettings(BaseModel):
    provider: str = os.getenv("AI_PROVIDER", "nvidia")
    model: str = os.getenv("AI_MODEL", "meta/llama-3.2-11b-vision-instruct")
    temperature: float = 0.7
    max_tokens: int = 500


class AppearanceSettings(BaseModel):
    opacity: float = 0.95
    font_size: int = 14
    theme: str = "dark"
    width: int = 460
    max_answer_height: int = 400
    show_question: bool = True
    show_sources: bool = True


class PrivacySettings(BaseModel):
    save_transcripts: bool = False
    save_audio: bool = False
    local_only_mode: bool = False


class SettingsResponse(BaseModel):
    general: GeneralSettings
    audio: AudioSettings
    ai: AISettings
    appearance: AppearanceSettings
    privacy: PrivacySettings


_settings = SettingsResponse(
    general=GeneralSettings(),
    audio=AudioSettings(),
    ai=AISettings(),
    appearance=AppearanceSettings(),
    privacy=PrivacySettings(),
)


@api_router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get all current settings."""
    return _settings


@api_router.put("/settings", response_model=SettingsResponse)
async def update_settings(updates: dict[str, Any]) -> SettingsResponse:
    """Update settings (partial update supported)."""
    global _settings

    if "general" in updates:
        _settings.general = GeneralSettings(**{
            **_settings.general.model_dump(),
            **updates["general"],
        })
    if "audio" in updates:
        _settings.audio = AudioSettings(**{
            **_settings.audio.model_dump(),
            **updates["audio"],
        })
    if "ai" in updates:
        _settings.ai = AISettings(**{
            **_settings.ai.model_dump(),
            **updates["ai"],
        })
    if "appearance" in updates:
        _settings.appearance = AppearanceSettings(**{
            **_settings.appearance.model_dump(),
            **updates["appearance"],
        })
    if "privacy" in updates:
        _settings.privacy = PrivacySettings(**{
            **_settings.privacy.model_dump(),
            **updates["privacy"],
        })

    logger.info("Settings updated")
    return _settings


# ─── API Connection & Keys Management ─────────────────────────────────────────

class TestKeyRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None


class SaveKeysRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None


def _persist_env_file_var(var_name: str, value: str) -> None:
    """Safely persist variable into .env files on disk."""
    for env_path in [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"),
        ".env",
        "backend/.env",
    ]:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                found = False
                new_lines = []
                for line in lines:
                    if line.strip().startswith(f"{var_name}=") and not line.strip().startswith("#"):
                        new_lines.append(f"{var_name}={value}\n")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f"{var_name}={value}\n")
                with open(env_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            except Exception:
                pass


@api_router.post("/settings/test-key")
async def test_key_endpoint(req: TestKeyRequest):
    """Test if user-provided API key is valid and working."""
    from app.ai.verifier import test_api_connection
    key = req.api_key.strip() if req.api_key else ""
    if not key:
        from app.settings.config import settings
        prov = req.provider.lower().strip()
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

    return await test_api_connection(
        provider=req.provider,
        api_key=key,
        model=req.model,
    )


@api_router.get("/settings/api-keys")
async def get_api_keys_info():
    """Get active provider and masked key previews."""
    import os
    from app.settings.config import settings

    claude_key = settings.claude_api_key or os.getenv("CLAUDE_API_KEY") or ""
    openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY") or ""
    gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or ""
    nvidia_key = settings.nvidia_api_key or os.getenv("NVIDIA_API_KEY") or ""
    hf_token = settings.hf_token or os.getenv("HF_TOKEN") or ""

    def mask(k: str) -> str:
        if not k or k.startswith("your_"):
            return ""
        if len(k) <= 8:
            return "••••••••"
        return f"{k[:4]}••••••••{k[-4:]}"

    return {
        "active_provider": _settings.ai.provider,
        "active_model": _settings.ai.model,
        "providers": {
            "claude": {"configured": bool(claude_key and not claude_key.startswith("your_")), "preview": mask(claude_key)},
            "openai": {"configured": bool(openai_key and not openai_key.startswith("your_")), "preview": mask(openai_key)},
            "gemini": {"configured": bool(gemini_key and not gemini_key.startswith("your_")), "preview": mask(gemini_key)},
            "nvidia": {"configured": bool(nvidia_key and not nvidia_key.startswith("your_")), "preview": mask(nvidia_key)},
            "huggingface": {"configured": bool(hf_token and not hf_token.startswith("your_")), "preview": mask(hf_token)},
        },
    }


@api_router.post("/settings/api-keys")
async def save_api_keys(req: SaveKeysRequest):
    """Save active provider and update credentials."""
    import os
    from app.settings.config import settings

    prov = req.provider.lower().strip()
    _settings.ai.provider = prov
    if req.model:
        _settings.ai.model = req.model
        os.environ["AI_MODEL"] = req.model
        _persist_env_file_var("AI_MODEL", req.model)

    key = (req.api_key or "").strip()
    if key:
        if prov in ("claude", "anthropic"):
            settings.claude_api_key = key
            os.environ["CLAUDE_API_KEY"] = key
            _persist_env_file_var("CLAUDE_API_KEY", key)
        elif prov == "openai":
            settings.openai_api_key = key
            os.environ["OPENAI_API_KEY"] = key
            _persist_env_file_var("OPENAI_API_KEY", key)
        elif prov in ("gemini", "google"):
            settings.gemini_api_key = key
            os.environ["GEMINI_API_KEY"] = key
            _persist_env_file_var("GEMINI_API_KEY", key)
        elif prov in ("nvidia", "deepseek"):
            settings.nvidia_api_key = key
            os.environ["NVIDIA_API_KEY"] = key
            _persist_env_file_var("NVIDIA_API_KEY", key)
        elif prov in ("huggingface", "hf"):
            settings.hf_token = key
            os.environ["HF_TOKEN"] = key
            _persist_env_file_var("HF_TOKEN", key)

    os.environ["AI_PROVIDER"] = prov
    _persist_env_file_var("AI_PROVIDER", prov)
    logger.info("Saved AI provider settings", provider=prov, model=_settings.ai.model)
    return {"status": "saved", "provider": prov, "model": _settings.ai.model}


# ─── Knowledge Base (FTS5 + PDF / Text Details) ───────────────────────────────

class AddTextRequest(BaseModel):
    title: str
    content: str
    doc_type: str = "note"


class SearchKnowledgeRequest(BaseModel):
    query: str
    limit: int = 4


@api_router.get("/knowledge")
async def list_knowledge_docs():
    """List all indexed documents in knowledge base."""
    from app.knowledge.store import KnowledgeStore
    store = KnowledgeStore.get_instance()
    return store.list_documents()


@api_router.post("/knowledge/text")
async def add_knowledge_text(req: AddTextRequest):
    """Add text details, experience, or notes to knowledge base."""
    from app.knowledge.store import KnowledgeStore
    store = KnowledgeStore.get_instance()
    try:
        doc = store.add_text_document(
            title=req.title,
            content=req.content,
            doc_type=req.doc_type,
        )
        return doc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/knowledge/upload")
async def upload_knowledge_pdf(file: Any = None):
    """Stub redirecting to multipart upload."""
    raise HTTPException(status_code=400, detail="Use /knowledge/upload-file multipart form")


@api_router.post("/knowledge/upload-file")
async def upload_pdf_file_endpoint(file: UploadFile = File(...)):
    """Upload PDF file (resume, notes, specs), extract text, and index into knowledge base."""
    from app.knowledge.store import KnowledgeStore

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        store = KnowledgeStore.get_instance()
        doc = store.add_pdf_document(filename=file.filename, file_bytes=content)
        return doc
    except Exception as e:
        logger.error("Failed to process uploaded PDF", filename=file.filename, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/knowledge/search")
async def search_knowledge(req: SearchKnowledgeRequest):
    """Search knowledge base with FTS5 BM25 relevance ranking."""
    from app.knowledge.store import KnowledgeStore
    store = KnowledgeStore.get_instance()
    return store.search(query=req.query, limit=req.limit)


@api_router.delete("/knowledge/{doc_id}")
async def delete_knowledge_doc(doc_id: str):
    """Delete document from knowledge base."""
    from app.knowledge.store import KnowledgeStore
    store = KnowledgeStore.get_instance()
    deleted = store.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "id": doc_id}



# ─── Sessions ─────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    mode: str = "interview"
    ai_provider: str = "claude"
    stt_provider: str = "none"


class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    status: str
    mode: str


_sessions: dict[str, SessionResponse] = {}


@api_router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest) -> SessionResponse:
    """Create a new session."""
    import uuid
    session_id = str(uuid.uuid4())
    session = SessionResponse(
        session_id=session_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="active",
        mode=request.mode,
    )
    _sessions[session_id] = session
    logger.info("Session created", session_id=session_id, mode=request.mode)
    return session


@api_router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get session by ID."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return _sessions[session_id]


@api_router.put("/sessions/{session_id}/stop", response_model=SessionResponse)
async def stop_session(session_id: str) -> SessionResponse:
    """Stop an active session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    _sessions[session_id].status = "stopped"
    logger.info("Session stopped", session_id=session_id)
    return _sessions[session_id]


# ─── Shutdown ─────────────────────────────────────────────────────────────────

@api_router.post("/shutdown")
async def shutdown() -> dict[str, str]:
    """Graceful shutdown endpoint (called by Electron before exit)."""
    import asyncio
    import os
    import signal
    logger.info("Shutdown requested")
    asyncio.get_event_loop().call_later(0.5, os.kill, os.getpid(), signal.SIGTERM)
    return {"status": "shutting_down"}
