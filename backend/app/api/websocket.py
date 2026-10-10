"""
WebSocket event handler — /ws/events
Bidirectional event stream between Electron and Python backend.
Integrates AudioManager for dual-stream audio capture and ChatEngine for live AI chat.
"""

import os
import uuid
import json
import time
import asyncio
import base64
from datetime import datetime, timezone
from typing import Any, Optional
import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.audio.manager import AudioManager
from app.audio.types import AudioSourceType
from app.ai.chat import ChatEngine
from app.stt.transcriber import get_transcriber
from app.logging.logger import get_logger

logger = get_logger(__name__)
ws_router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected", total=len(self.active_connections))

    async def send_event(
        self,
        websocket: WebSocket,
        event_type: str,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> None:
        """Send a typed event envelope to a specific client."""
        if websocket.client_state != WebSocketState.CONNECTED:
            return

        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "payload": payload,
        }
        await websocket.send_text(json.dumps(event))

    async def broadcast_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> None:
        """Broadcast a typed event to all connected clients."""
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "payload": payload,
        }
        message = json.dumps(event)
        disconnected = []

        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()

# Global ChatEngine instance
chat_engine = ChatEngine()

# Deduplication & debouncing state for AI co-pilot prompts
_last_ai_prompt: str = ""
_last_ai_time: float = 0.0
_ai_lock = asyncio.Lock()
_current_abort_event = asyncio.Event()
is_listening_active: bool = True


async def handle_speech_final(speaker: str, text: str) -> None:
    """
    Handle final transcribed speech segment from microphone or system speaker.
    Whenever a gap in speech occurs, automatically stream an AI co-pilot response.
    Deduplicates across both microphone and system streams to prevent duplicate executions.
    """
    global _last_ai_prompt, _last_ai_time, is_listening_active

    if not is_listening_active and not audio_manager.is_capturing:
        return

    clean_text = text.strip()
    if not clean_text or len(clean_text) < 3:
        return

    # In dual-stream mode (BOTH), only the INTERVIEWER asking a question triggers AI co-pilot answers.
    # The interviewee (local user) answering does not trigger an AI answer to their own voice.
    if speaker == "interviewee" and audio_manager.current_source == AudioSourceType.BOTH:
        logger.debug("Skipping AI generation for local interviewee speech in dual mode", text=clean_text)
        return

    # Normalize text for deduplication (strip punctuation, whitespace, lowercase)
    import re
    norm_text = re.sub(r"[^\w\s]", "", clean_text).lower().strip()
    now_ts = time.time()

    # Deduplicate: if the same prompt arrived within 4.0 seconds (e.g. mic acoustic bleed or re-segmentation), skip
    if norm_text == _last_ai_prompt and (now_ts - _last_ai_time) < 4.0:
        logger.info("Ignoring duplicate speech AI prompt", prompt=clean_text, speaker=speaker)
        return

    # Debounce rapid triggers within 1.0 second
    if (now_ts - _last_ai_time) < 1.0:
        logger.info("Debouncing rapid speech prompt", prompt=clean_text, speaker=speaker)
        return

    _last_ai_prompt = norm_text
    _last_ai_time = now_ts

    q_id = f"speech_{uuid.uuid4().hex[:8]}"
    logger.info(
        "Finalized speech segment received, generating AI response",
        speaker=speaker,
        question_id=q_id,
        text=clean_text,
    )

    # License & Free Usage limit verification
    try:
        from app.ota.agent.license_client import ClientLicenseManager
        from app.database.engine import AsyncSessionLocal
        from app.ota.usage_service import record_usage_event
        from app.ota.agent.identity import get_or_create_device_id, get_device_token

        lic_mgr = ClientLicenseManager()
        if not lic_mgr.is_allowed():
            state = lic_mgr.current_state
            await manager.broadcast_event(
                "license.blocked",
                {
                    "device_id": state.get("device_id"),
                    "status": "blocked",
                    "usage_consumed": state.get("usage_consumed", 100),
                    "usage_limit": state.get("usage_limit", 100),
                    "contact_name": state.get("contact_name", "Diwakar"),
                    "support_message": state.get("support_message", "For access activation or license upgrade."),
                },
            )
            return

        async with AsyncSessionLocal() as session:
            usage_res = await record_usage_event(
                session=session,
                device_id=get_or_create_device_id(),
                device_token=get_device_token(),
                event_type="speech_transcription",
                application_version="0.1.0",
            )
            await manager.broadcast_event("license.status", usage_res)
    except Exception as lic_err:
        logger.warning("License check exception (proceeding)", error=str(lic_err))

    # 1. Dispatch question / speech prompt detected event
    await manager.broadcast_event(
        "question.detected",
        {
            "question_id": q_id,
            "question": clean_text,
            "category": "speech",
            "confidence": 0.95,
            "is_followup": False,
            "speaker": speaker,
        },
    )

    try:
        from app.api.routes import _settings
        provider = getattr(_settings.ai, "provider", None) or os.getenv("AI_PROVIDER", "nvidia")
        model = getattr(_settings.ai, "model", None) or os.getenv("AI_MODEL", "meta/llama-3.2-11b-vision-instruct")
    except Exception:
        provider = os.getenv("AI_PROVIDER", "nvidia")
        model = os.getenv("AI_MODEL", "meta/llama-3.2-11b-vision-instruct")

    # 2. Dispatch ai.request.started
    await manager.broadcast_event(
        "ai.request.started",
        {
            "question_id": q_id,
            "speaker": speaker,
            "prompt": clean_text,
            "provider": provider,
            "model": model,
        },
    )

    # 3. Stream AI answer tokens directly to the chat
    full_answer = ""
    start_time = datetime.now(timezone.utc)
    _current_abort_event.clear()
    try:
        async with _ai_lock:
            async for token in chat_engine.stream_response(prompt=clean_text):
                if _current_abort_event.is_set():
                    logger.info("AI speech streaming cancelled by user", question_id=q_id)
                    await manager.broadcast_event(
                        "ai.cancelled",
                        {"question_id": q_id, "reason": "user_stopped"},
                    )
                    return
                full_answer += token
                await manager.broadcast_event(
                    "ai.token",
                    {"question_id": q_id, "token": token},
                )
    except Exception as e:
        logger.error("Error during AI response streaming", error=str(e))
        full_answer = f"Error generating answer: {str(e)}"
        await manager.broadcast_event(
            "ai.token",
            {"question_id": q_id, "token": full_answer},
        )

    # 4. Dispatch ai.completed
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    await manager.broadcast_event(
        "ai.completed",
        {
            "question_id": q_id,
            "answer": full_answer,
            "tokens_used": len(full_answer.split()),
            "latency_ms": duration_ms,
            "sources": [],
        },
    )


# Global AudioManager instance configured to broadcast dual-stream audio events
audio_manager = AudioManager(
    event_callback=lambda event_type, payload: manager.broadcast_event(event_type, payload),
    on_speech_final=handle_speech_final,
)


async def handle_command(
    websocket: WebSocket,
    command_type: str,
    payload: dict[str, Any],
) -> None:
    """Handle incoming commands from the Electron frontend."""
    global is_listening_active
    logger.debug("Command received", type=command_type, payload=payload)

    if command_type == "command.toggle_listening":
        if is_listening_active or audio_manager.is_capturing:
            is_listening_active = False
            await audio_manager.stop()
            await manager.broadcast_event(
                "session.state_changed",
                {"previous": "LISTENING", "current": "IDLE"},
            )
        else:
            is_listening_active = True
            source_str = payload.get("source", "both")
            if source_str == "microphone":
                source = AudioSourceType.MICROPHONE
            elif source_str == "system":
                source = AudioSourceType.SYSTEM
            else:
                source = AudioSourceType.BOTH

            device_id = payload.get("device_id")
            await audio_manager.start(source=source, device_id=device_id)
            await manager.broadcast_event(
                "session.state_changed",
                {"previous": "IDLE", "current": "LISTENING"},
            )

    elif command_type == "command.start_listening":
        is_listening_active = True
        from app.ota.agent.license_client import ClientLicenseManager
        lic_mgr = ClientLicenseManager()
        if not lic_mgr.is_allowed():
            state = lic_mgr.current_state
            await manager.send_event(
                websocket,
                "license.blocked",
                {
                    "device_id": state.get("device_id"),
                    "status": "blocked",
                    "usage_consumed": state.get("usage_consumed", 100),
                    "usage_limit": state.get("usage_limit", 100),
                    "contact_name": state.get("contact_name", "Diwakar"),
                    "support_message": state.get("support_message", "For access activation or license upgrade."),
                },
            )
            return

        source_str = payload.get("source", "both")
        if source_str == "microphone":
            source = AudioSourceType.MICROPHONE
        elif source_str == "system":
            source = AudioSourceType.SYSTEM
        else:
            source = AudioSourceType.BOTH

        device_id = payload.get("device_id")
        await audio_manager.start(source=source, device_id=device_id)
        await manager.broadcast_event(
            "session.state_changed",
            {"previous": "IDLE", "current": "LISTENING"},
        )

    elif command_type in ("command.device_handshake", "command.client_heartbeat"):
        try:
            from app.database.engine import AsyncSessionLocal
            from app.ota.device_service import register_or_update_device
            from app.ota.schemas import DeviceRegisterRequest
            from app.ota.license_service import validate_device_license

            dev_id = payload.get("device_id")
            if dev_id:
                async with AsyncSessionLocal() as db_session:
                    reg_req = DeviceRegisterRequest(
                        device_id=dev_id,
                        device_name=payload.get("device_name") or payload.get("hostname") or f"SUT-{dev_id[:8]}",
                        hostname=payload.get("hostname") or f"SUT-{dev_id[:8]}",
                        os=payload.get("os") or "Windows",
                        os_version=payload.get("os_version") or "10/11",
                        cpu=payload.get("cpu") or "4 Cores",
                        ram=payload.get("ram") or "8 GB",
                        disk_space=payload.get("disk_space") or "50 GB",
                        application_version=payload.get("application_version") or payload.get("app_version") or "0.1.0",
                        agent_version=payload.get("agent_version") or "1.0.0",
                    )
                    dev, tok = await register_or_update_device(db_session, reg_req)
                    logger.info("SUT presence updated via WebSocket handshake", device_id=dev_id, hostname=dev.hostname)

                    lic_info = await validate_device_license(db_session, dev_id, tok, "0.1.0")
                    await manager.send_event(websocket, "license.status", lic_info)
                    if lic_info.get("is_blocked") or lic_info.get("status") == "blocked":
                        await manager.send_event(websocket, "license.blocked", lic_info)
        except Exception as e:
            logger.warning("Error in device handshake handler", error=str(e))

    elif command_type == "command.sync_license":
        try:
            from app.database.engine import AsyncSessionLocal
            from app.ota.agent.identity import get_or_create_device_id, get_device_token
            from app.ota.license_service import validate_device_license
            from app.ota.agent.license_client import ClientLicenseManager

            async with AsyncSessionLocal() as db_session:
                dev_id = payload.get("device_id") or get_or_create_device_id()
                dev_tok = payload.get("device_token") or get_device_token()
                lic_data = await validate_device_license(db_session, dev_id, dev_tok, "0.1.0")

            lic_mgr = ClientLicenseManager()
            lic_mgr.current_state.update(lic_data)
            lic_mgr._save_cache(lic_mgr.current_state)

            await manager.send_event(websocket, "license.status", lic_data)
            if lic_data.get("is_blocked") or lic_data.get("status") == "blocked":
                await manager.send_event(websocket, "license.blocked", lic_data)
        except Exception as e:
            logger.debug("License sync command error", error=str(e))

    elif command_type == "command.stop_listening":
        is_listening_active = False
        await audio_manager.stop()
        await manager.broadcast_event(
            "session.state_changed",
            {"previous": "LISTENING", "current": "IDLE"},
        )

    elif command_type == "command.speech_input":
        text = (payload.get("text") or "").strip()
        speaker = payload.get("speaker", "interviewer")
        if text:
            logger.info("Received client speech input", speaker=speaker, text=text)
            await manager.broadcast_event(
                "speech.final",
                {
                    "speaker": speaker,
                    "text": text,
                    "confidence": payload.get("confidence", 0.95),
                },
            )
            await handle_speech_final(speaker, text)

    elif command_type == "command.speech_partial":
        text = (payload.get("text") or "").strip()
        speaker = payload.get("speaker", "interviewer")
        if text:
            await manager.broadcast_event(
                "speech.partial",
                {
                    "speaker": speaker,
                    "text": text,
                },
            )

    elif command_type == "command.client_vad_state":
        speaker = payload.get("speaker", "interviewer")
        state = payload.get("state", "SILENCE")
        await manager.broadcast_event(
            "audio.vad_state_changed",
            {
                "speaker": speaker,
                "state": state,
            },
        )

    elif command_type == "command.audio_chunk":
        b64_data = payload.get("data")
        speaker = payload.get("speaker", "interviewer")
        if b64_data and is_listening_active:
            try:
                raw_bytes = base64.b64decode(b64_data)
                int16_arr = np.frombuffer(raw_bytes, dtype=np.int16)
                float32_arr = int16_arr.astype(np.float32) / 32767.0

                transcriber = get_transcriber()
                chunk_text = await asyncio.to_thread(transcriber.transcribe, float32_arr)
                chunk_text = chunk_text.strip() if chunk_text else ""
                if chunk_text:
                    logger.info("Transcribed client audio chunk", speaker=speaker, text=chunk_text)
                    await manager.broadcast_event(
                        "speech.final",
                        {
                            "speaker": speaker,
                            "text": chunk_text,
                            "confidence": 0.95,
                        },
                    )
                    await handle_speech_final(speaker, chunk_text)
            except Exception as e:
                logger.error("Error processing client audio chunk", error=str(e))

    elif command_type == "command.set_mode":
        mode = payload.get("mode", "interview")
        logger.info("Mode changed", mode=mode)
        await manager.send_event(
            websocket,
            "session.state_changed",
            {"mode": mode},
        )

    elif command_type == "command.chat_message":
        # Interactive Chatbot request
        prompt = (payload.get("prompt") or payload.get("message") or "").strip()
        history = payload.get("history", [])
        msg_id = payload.get("message_id") or str(uuid.uuid4())
        logger.info("Processing chat message", msg_id=msg_id, prompt=prompt[:50] if prompt else "")

        # License & Free Usage limit verification
        try:
            from app.ota.agent.license_client import ClientLicenseManager
            from app.database.engine import AsyncSessionLocal
            from app.ota.usage_service import record_usage_event
            from app.ota.agent.identity import get_or_create_device_id, get_device_token

            lic_mgr = ClientLicenseManager()
            if not lic_mgr.is_allowed():
                state = lic_mgr.current_state
                await manager.send_event(
                    websocket,
                    "license.blocked",
                    {
                        "device_id": state.get("device_id"),
                        "status": "blocked",
                        "usage_consumed": state.get("usage_consumed", 100),
                        "usage_limit": state.get("usage_limit", 100),
                        "contact_name": state.get("contact_name", "Diwakar"),
                        "support_message": state.get("support_message", "For access activation or license upgrade."),
                    },
                )
                await manager.send_event(
                    websocket,
                    "chat.completed",
                    {
                        "message_id": msg_id,
                        "reply": "🔒 Access limit reached. Your free usage allowance has been exhausted. Please contact Diwakar for continued access.",
                    },
                )
                return

            async with AsyncSessionLocal() as session:
                usage_res = await record_usage_event(
                    session=session,
                    device_id=get_or_create_device_id(),
                    device_token=get_device_token(),
                    event_type="chat_message",
                    application_version="0.1.0",
                )
                await manager.broadcast_event("license.status", usage_res)
        except Exception as lic_err:
            logger.warning("License check exception in chat", error=str(lic_err))

        if prompt:
            full_response = ""
            _current_abort_event.clear()
            async for token in chat_engine.stream_response(prompt=prompt, history=history):
                if _current_abort_event.is_set():
                    logger.info("Chat streaming cancelled by user", message_id=msg_id)
                    await manager.send_event(
                        websocket,
                        "ai.cancelled",
                        {"message_id": msg_id, "reason": "user_stopped"},
                    )
                    return
                full_response += token
                await manager.send_event(
                    websocket,
                    "chat.token",
                    {"message_id": msg_id, "token": token},
                )

            await manager.send_event(
                websocket,
                "chat.completed",
                {"message_id": msg_id, "reply": full_response},
            )
        else:
            await manager.send_event(
                websocket,
                "chat.completed",
                {"message_id": msg_id, "reply": "Please provide a question or message."},
            )

    elif command_type in ("command.cancel", "command.stop_and_reset"):
        logger.info("Stop / Interrupt requested — halting AI generation and purging previous speech audio")
        global _last_ai_prompt, _last_ai_time
        _current_abort_event.set()

        # Flush backend audio frames and buffers so previous talk is dropped
        audio_manager.speech_frames["interviewer"] = []
        audio_manager.speech_frames["interviewee"] = []
        audio_manager.buffer.clear()
        audio_manager.vad_interviewer.reset()
        audio_manager.vad_interviewee.reset()
        audio_manager._last_transcribed_text = {
            "interviewer": ("", 0.0),
            "interviewee": ("", 0.0),
        }

        # Clear prompt deduplication state
        _last_ai_prompt = ""
        _last_ai_time = 0.0

        # Broadcast cancellation and clear interim transcripts
        await manager.broadcast_event(
            "ai.cancelled",
            {"reason": "user_stopped"},
        )
        await manager.broadcast_event(
            "speech.partial",
            {"speaker": "interviewer", "text": ""},
        )

        # Keep listening active for new incoming chats and talks
        is_listening_active = True
        await manager.broadcast_event(
            "session.state_changed",
            {"previous": "GENERATING", "current": "LISTENING"},
        )

    elif command_type == "command.regenerate":
        logger.info("Regenerate requested")

    else:
        logger.warning("Unknown command type", type=command_type)


@ws_router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """Main WebSocket endpoint for bidirectional event streaming."""
    await manager.connect(websocket)

    # Ensure a clean slate: wipe any stale frames or buffer chunks from previous sessions
    audio_manager.speech_frames["interviewer"] = []
    audio_manager.speech_frames["interviewee"] = []
    audio_manager.buffer.clear()
    audio_manager.vad_interviewer.reset()
    audio_manager.vad_interviewee.reset()

    lic_data = {}
    try:
        from app.database.engine import AsyncSessionLocal
        from app.ota.agent.identity import get_or_create_device_id, get_device_token
        from app.ota.license_service import validate_device_license
        from app.ota.agent.license_client import ClientLicenseManager

        async with AsyncSessionLocal() as db_session:
            dev_id = get_or_create_device_id()
            dev_tok = get_device_token()
            lic_data = await validate_device_license(db_session, dev_id, dev_tok, "0.1.0")

        lic_mgr = ClientLicenseManager()
        lic_mgr.current_state.update(lic_data)
        lic_mgr._save_cache(lic_mgr.current_state)
    except Exception as e:
        logger.debug("Initial license sync error", error=str(e))

    await manager.send_event(
        websocket,
        "connection.established",
        {
            "version": "0.1.0",
            "message": "AI Teleprompter backend connected",
            "audio_capturing": audio_manager.is_capturing,
            "device_id": dev_id,
            "device_token": dev_tok,
            "license": lic_data,
        },
    )
    if lic_data.get("is_blocked") or lic_data.get("status") == "blocked":
        await manager.send_event(websocket, "license.blocked", lic_data)

    # Auto-start dual-stream audio capture on connection (in live app)
    if not audio_manager.is_capturing and os.getenv("TESTING") != "1":
        started = await audio_manager.start(source=AudioSourceType.BOTH)
        if started:
            await manager.broadcast_event(
                "session.state_changed",
                {"previous": "IDLE", "current": "LISTENING"},
            )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                command_type = data.get("type", "")
                payload = data.get("payload", {})

                if command_type:
                    await handle_command(websocket, command_type, payload)

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from WebSocket client")
                await manager.send_event(
                    websocket,
                    "error.recoverable",
                    {"code": "INVALID_JSON", "message": "Message must be valid JSON"},
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if len(manager.active_connections) == 0:
            logger.info("All WebSocket clients disconnected; stopping audio capture to prevent background recording")
            await audio_manager.stop()
            audio_manager.speech_frames["interviewer"] = []
            audio_manager.speech_frames["interviewee"] = []
            audio_manager.buffer.clear()
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        manager.disconnect(websocket)
        if len(manager.active_connections) == 0:
            await audio_manager.stop()
