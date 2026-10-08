# AI Teleprompter — Architecture

## Overview

AI Teleprompter is a production-quality desktop application that captures permitted system audio,
transcribes speech in real time, detects questions, retrieves relevant user-provided context,
and displays concise AI-generated answers in a minimal transparent overlay.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ELECTRON                             │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Main Process│    │  Preload     │    │  Renderer    │  │
│  │  (Node.js)   │◄──►│  (Bridge)    │◄──►│  (React/TS)  │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                   │
│         │  Secure IPC (contextBridge)                       │
│         │  Local WebSocket (127.0.0.1)                      │
└─────────┼───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  PYTHON APPLICATION ENGINE                  │
│                     (FastAPI / asyncio)                     │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Audio   │  │   STT    │  │ Question │  │ Context  │   │
│  │  Engine  │─►│  Engine  │─►│  Engine  │─►│  Engine  │   │
│  └──────────┘  └──────────┘  └──────────┘  └────┬─────┘   │
│                                                  │         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────▼─────┐   │
│  │  Answer  │◄─│AI Gateway│◄─│  RAG     │◄─│ Retrieval│   │
│  │  Engine  │  │          │  │  Engine  │  │  Engine  │   │
│  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘   │
│       │                                                     │
│  ┌────▼─────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Session  │  │ Settings │  │ Security │  │ Database │   │
│  │ Manager  │  │ Manager  │  │ Manager  │  │ (SQLite) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### Electron Main Process
- Window lifecycle management (create, show, hide, destroy)
- System tray integration
- Global keyboard shortcut registration
- Secure credential storage (OS keychain via `keytar`)
- IPC message routing between renderer and backend
- Backend process spawning and lifecycle management
- Screen/monitor enumeration
- Click-through toggling (via `setIgnoreMouseEvents`)

### Electron Preload
- Contextually isolated bridge between renderer and main process
- Exposes only safe, typed API surface via `contextBridge`
- No direct Node.js access from renderer

### Electron Renderer (React)
- Transparent overlay UI
- Zustand state management
- WebSocket client to Python backend
- UI-only logic — no business logic
- No API keys, no credentials

### Python Application Engine

**Audio Engine** — Captures system audio (WASAPI loopback) and/or microphone.
  Enumerates devices, resamples, converts to mono, runs VAD.

**STT Engine** — Abstract STT provider. Streams audio chunks to cloud/local STT.
  Emits partial and final transcript events.

**Question Engine** — Classifies transcripts. Detects questions.
  Resolves follow-ups. Maintains conversation context.

**Context Engine** — Manages the context library. Ingests documents.
  Maintains project profiles, resume, job description.

**RAG Engine** — Embedding provider abstraction. FAISS vector store.
  Retrieval pipeline with reranking and metadata filtering.

**AI Gateway** — Provider abstraction for Claude/OpenAI/Gemini/Ollama.
  Manages retries, timeouts, streaming, cancellation, token tracking.

**Answer Engine** — Generates answers using context + AI.
  Formats by mode. Validates answers against context.

**Session Manager** — Tracks active session state.
  Maintains conversation history, current topic, entities.

**Settings Manager** — Typed Pydantic settings. Persists to SQLite.
  Validates on startup.

**Security Manager** — API key encryption/decryption.
  File validation. Path normalization. Input sanitization.

**Database** — SQLite with SQLAlchemy. Migration management via Alembic.

---

## Communication Patterns

### Electron <-> Python
Primary: **WebSocket** at `ws://127.0.0.1:{port}/ws/events`
- Bidirectional streaming events
- JSON-encoded typed event envelopes
- Auth token validated on connection

Secondary: **HTTP REST** at `http://127.0.0.1:{port}/api/v1/`
- Settings CRUD, session management, context library management

### Main <-> Renderer
- `ipcMain` / `ipcRenderer` via `contextBridge`
- All channels explicitly allowlisted in preload
- No raw Node.js access from renderer

### Python Modules (Internal)
- Direct function calls (same process, asyncio)
- Event bus for cross-module notifications
- asyncio queues for audio/STT pipeline

---

## Security Model

1. **API keys never reach the renderer.**
2. **Backend binds to 127.0.0.1 only.** Never `0.0.0.0`.
3. **WebSocket auth token.** Generated on startup, required for WS connection.
4. **contextIsolation = true, nodeIntegration = false** in Electron renderer.
5. **Preload allowlist.** Only explicitly exported functions are available to renderer JS.
6. **File security.** Extension + MIME validation, size limits, path normalization.
7. **Prompt injection protection.** Document content is reference material only.
8. **No plaintext secrets in database.**

### Trust Boundaries
```
UNTRUSTED: Renderer JS, uploaded documents, transcribed text
SEMI-TRUSTED: Python backend (local), Electron main
TRUSTED: OS keychain, user-confirmed settings
```

---

## Database Design

- **settings** — Application configuration (key/value JSON)
- **sessions** — Recording sessions with metadata
- **messages** — Transcript + Q&A per session
- **documents** — Ingested file metadata (path, hash, type, enabled)
- **document_chunks** — Chunked document text with page references
- **contexts** — Named context groups (resume, project, JD)
- **projects** — Structured project profiles
- **shortcuts** — User-customized keyboard shortcuts
- **provider_configs** — STT/AI provider parameters (no secrets)
- **usage** — Internal latency/token metrics (local only)

### Migration Strategy
- Alembic for schema versioning
- `alembic upgrade head` on every startup
- Never `DROP TABLE` in normal operation

---

## Event System

All events use this envelope:
```json
{
  "id": "<uuid4>",
  "type": "namespace.event_name",
  "timestamp": "<ISO8601>",
  "session_id": "<uuid4 | null>",
  "payload": {}
}
```

Event namespaces: `session`, `audio`, `speech`, `question`, `context`, `ai`, `overlay`, `error`

---

## Provider Abstraction

Every external integration uses an abstract base class:
- `STTProvider` — streaming audio -> transcript
- `EmbeddingProvider` — text -> float vector
- `VectorStore` — add/search/delete vectors
- `AIProvider` — generate/stream/vision

---

## State Machine

```
IDLE -> LISTENING -> SPEECH_DETECTED -> TRANSCRIBING
-> QUESTION_DETECTED -> RETRIEVING -> GENERATING
-> DISPLAYING -> IDLE

Any state -> ERROR -> RECOVERING -> previous stable state
```

---

## Error Handling

- Typed exception hierarchy
- All errors caught at module boundaries
- Errors emit structured events to WebSocket clients
- UI shows user-friendly messages, never raw exceptions

---

## Testing Strategy

- **Unit**: Pure functions, mocked I/O, no API keys required
- **Integration**: Mocked STT/AI providers, real database
- **E2E**: Deterministic text injection -> question -> mocked context -> answer validation
- **Evaluation**: Dataset-driven groundedness + latency benchmarks
