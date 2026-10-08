# AI Teleprompter — Development Plan

## Development Phases

### Phase 0: Architecture (COMPLETE)
- [x] docs/architecture.md
- [x] docs/technical-decisions.md
- [x] docs/development-plan.md
- [x] docs/api.md
- [x] docs/events.md
- [x] Repository structure

### Phase 1: Foundation (COMPLETE)
- [x] Electron + React + TypeScript + Tailwind
- [x] Vite build system
- [x] Transparent frameless window
- [x] Always-on-top
- [x] Click-through toggle
- [x] Opacity control
- [x] Overlay UI (status, question, answer)
- [x] Global hotkeys
- [x] System tray
- [x] FastAPI backend (health, settings, sessions)
- [x] WebSocket /ws/events
- [x] Frontend WebSocket client
- [x] Connection status display
- [x] Graceful shutdown

### Phase 2: Audio Engine (COMPLETE)
- [x] Audio device enumeration (MME, DirectSound, WASAPI, WDM-KS)
- [x] WASAPI loopback support (System Audio capture)
- [x] Microphone capture
- [x] Resampling + mono conversion (16kHz PCM16 pipeline)
- [x] VAD (adaptive energy-based state machine)
- [x] Audio event emission (`audio.started`, `audio.stopped`, `audio.vad_state_changed`, `audio.error`)

### Phase 3: STT Engine
- [ ] STTProvider abstract base class
- [ ] Streaming STT provider (Deepgram)
- [ ] Partial + final transcript events
- [ ] FasterWhisperProvider (feature-flagged)

### Phase 4: Question Engine
- [ ] QuestionDetector
- [ ] QuestionClassifier
- [ ] FollowUpResolver
- [ ] QuestionQueue
- [ ] Conversation memory

### Phase 5: AI Integration
- [ ] AIProvider abstract base class
- [ ] ClaudeProvider (streaming)
- [ ] AIGateway (retries, fallback, cancellation)
- [ ] Prompt management
- [ ] Answer Engine
- [ ] Answer streaming to UI

### Phase 6: Context + RAG
- [ ] EmbeddingProvider (SentenceTransformers)
- [ ] VectorStore (FAISS)
- [ ] Document chunker
- [ ] PDF parser (PyMuPDF)
- [ ] Context library UI
- [ ] Drag-and-drop ingestion
- [ ] Context builder
- [ ] Retrieval pipeline

### Phase 7: Screenshot + Vision
- [ ] Screenshot hotkey
- [ ] Region selection
- [ ] Vision provider
- [ ] Image context

### Phase 8: Advanced Features
- [ ] Answer modes (Short/Technical/Behavioral/etc.)
- [ ] Code context + syntax highlighting
- [ ] Project profiles
- [ ] Resume profile
- [ ] Job description
- [ ] Clipboard integration

### Phase 9: Offline Mode
- [ ] FasterWhisper integration
- [ ] Ollama provider
- [ ] Offline mode toggle
- [ ] Local-only operation

### Phase 10: Settings + UX
- [ ] Full settings UI
- [ ] Command palette
- [ ] Developer debug panel
- [ ] Multi-monitor support
- [ ] Accessibility

### Phase 11: Security Hardening
- [ ] API key rotation
- [ ] Audit logging
- [ ] File security hardening
- [ ] Prompt injection testing

### Phase 12: Testing + Quality
- [ ] Complete unit test suite
- [ ] Integration tests
- [ ] E2E tests
- [ ] AI evaluation datasets
- [ ] Performance benchmarks

### Phase 13: Packaging
- [ ] electron-builder configuration
- [ ] NSIS installer
- [ ] Auto-update (optional)
- [ ] Code signing (optional)
- [ ] Release pipeline

---

## Development Principles

1. Each phase must compile, run, have tests, and not break prior phases.
2. Tests run before moving to next phase.
3. Linting and type checking on every phase.
4. No phase skipped without explicit user approval.
5. Application must start and show the overlay at every phase.
