# AI Teleprompter — Technical Decisions

## TD-001: Electron + React for Desktop
**Decision**: Use Electron with React/TypeScript for the desktop shell.
**Rationale**: Cross-platform capable, mature ecosystem, supports transparent frameless windows, system tray, global shortcuts, and screen capture APIs. React + TypeScript provides type safety and component reuse.
**Alternatives considered**: Tauri (immature audio/screen capture), raw Win32 (not cross-platform capable), Qt (no easy AI streaming UI).
**Trade-offs**: Higher memory than native; mitigated by Electron's performance improvements in v24+.

## TD-002: Python FastAPI Backend
**Decision**: Python 3.11+ + FastAPI + asyncio for the application engine.
**Rationale**: Python has the best AI/ML library ecosystem (sentence-transformers, FAISS, whisper, anthropic SDK). FastAPI provides async WebSockets natively. asyncio allows non-blocking audio + STT + AI simultaneously.
**Alternatives considered**: Node.js backend (poor ML library support), Rust (development velocity).
**Trade-offs**: Two runtimes (Electron + Python); mitigated by spawning Python as child process managed by Electron.

## TD-003: SQLite for Persistence
**Decision**: SQLite with SQLAlchemy ORM and Alembic migrations.
**Rationale**: Zero-config, single-file, sufficient for local desktop use. No network dependency. SQLAlchemy provides ORM and migration support via Alembic.
**Alternatives considered**: PostgreSQL (overkill for local), DynamoDB (cloud dependency), JSON files (no query capability).

## TD-004: FAISS for Vector Search
**Decision**: FAISS (Facebook AI Similarity Search) for local vector indexing.
**Rationale**: Runs entirely locally. No cloud dependency. Extremely fast for the library sizes expected (<100k chunks). Well-maintained by Meta.
**Alternatives considered**: Chroma (heavier), Pinecone (cloud), Weaviate (Docker required).
**Metadata**: Stored in SQLite alongside FAISS. FAISS stores only float32 vectors + integer IDs.

## TD-005: Sentence Transformers for Embeddings
**Decision**: `all-MiniLM-L6-v2` as default embedding model.
**Rationale**: 384-dimensional, ~80MB, fast inference on CPU, excellent semantic quality for the use case. Fully local, no API cost.
**Alternatives considered**: OpenAI embeddings (API cost + latency), large models (too slow on CPU).
**Configurable**: Provider abstraction allows swapping to OpenAI or other models.

## TD-006: WebSocket for Real-Time Events
**Decision**: WebSocket at `ws://127.0.0.1:8765/ws/events` for Electron <-> Python communication.
**Rationale**: Bidirectional streaming required for audio pipeline events, partial STT transcripts, and streaming AI tokens. HTTP polling would introduce unacceptable latency.
**Security**: Auth token in connection handshake. Bound to localhost only.

## TD-007: Claude as Initial AI Provider
**Decision**: Anthropic Claude (claude-3-5-sonnet) as the initial AI provider.
**Rationale**: Excellent instruction following, low hallucination rate, strong coding and technical reasoning. Streaming API available.
**Abstraction**: `AIProvider` ABC ensures provider can be swapped without changing Answer Engine logic.

## TD-008: Vite for Frontend Bundling
**Decision**: Vite + electron-vite for the Electron renderer.
**Rationale**: Fast HMR, native ESM, TypeScript support, Tailwind integration. electron-vite handles main/preload/renderer split properly.
**Alternatives considered**: Webpack (slow), CRA (deprecated), Parcel (less Electron support).

## TD-009: Zustand for Frontend State
**Decision**: Zustand for client-side state management.
**Rationale**: Minimal boilerplate, TypeScript-friendly, no provider wrapping needed, devtools available. Perfect for the per-module stores pattern.
**Alternatives considered**: Redux (too verbose), Jotai (less familiar), Context API (performance issues with frequent updates).

## TD-010: Keytar for Credential Storage
**Decision**: `keytar` npm package for OS keychain integration.
**Rationale**: Uses Windows Credential Manager, macOS Keychain, libsecret on Linux. API keys never stored in plaintext.
**Alternative**: `electron-store` with encryption — decided against because keytar uses the OS security subsystem directly.

## TD-011: Alembic for Database Migrations
**Decision**: Alembic for database migrations from day one.
**Rationale**: Prevents schema drift. Enables safe upgrades. Required for any production application.
**Policy**: Never use `Base.metadata.create_all()` without a corresponding migration.

## TD-012: Pydantic Settings
**Decision**: Pydantic v2 BaseSettings for Python configuration.
**Rationale**: Type-safe configuration, environment variable loading, validation on startup. Fails fast if misconfigured.

## TD-013: VAD Before STT
**Decision**: Voice Activity Detection before sending audio to STT.
**Rationale**: Reduces STT API costs. Reduces latency by not sending silence. Reduces irrelevant transcripts.
**Implementation**: Energy-based VAD as default, silero-vad as optional upgrade.

## TD-014: No Docker for MVP
**Decision**: No Docker containerization for MVP.
**Rationale**: Desktop application — containers add complexity without benefit. Users would need Docker installed. Electron manages the Python process directly.
**Future**: Docker could be useful for CI testing environments.

## TD-015: PyMuPDF for PDF Parsing
**Decision**: PyMuPDF (fitz) for PDF text extraction.
**Rationale**: Fast, accurate, preserves page numbers, handles complex layouts better than PyPDF2. Open source.

## TD-016: Chunk Size 500-800 Tokens
**Decision**: Document chunks of 500-800 tokens with 50-100 token overlap.
**Rationale**: Large enough for meaningful context, small enough for precise retrieval. Overlap preserves context at chunk boundaries.
**Configurable**: Per-context-type chunking strategies planned.

## TD-017: Context Priority Tiers
**Decision**: Six-tier context priority system (P0-P5).
**Rationale**: Not all context is equally relevant. Current question context > resume > general documents. Enforces token budget discipline.

## TD-018: Answer Streaming
**Decision**: Stream AI tokens from Python -> WebSocket -> Electron -> React as they arrive.
**Rationale**: Reduces perceived latency significantly. User sees answer appearing rather than waiting for complete response.
**Implementation**: AsyncGenerator in Python, streamed over WebSocket as individual token events.

## TD-019: WASAPI Loopback for System Audio
**Decision**: WASAPI loopback capture for system audio on Windows.
**Rationale**: Captures audio output without a virtual cable. Native Windows API. No third-party driver required.
**Library**: `sounddevice` or `pyaudiowpatch` for WASAPI loopback support.

## TD-020: electron-builder for Packaging
**Decision**: electron-builder for creating Windows installers.
**Rationale**: Mature, NSIS installer support, auto-update support, code signing support.
**Artifacts**: NSIS installer (.exe), portable (.exe).
