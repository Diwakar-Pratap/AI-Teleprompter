# AI Teleprompter — Event System

## Event Envelope

All WebSocket messages use this envelope:
```json
{
  "id": "<uuid4>",
  "type": "<namespace>.<event_name>",
  "timestamp": "<ISO8601>",
  "session_id": "<uuid4 | null>",
  "payload": {}
}
```

---

## Session Events

### session.started
```json
{
  "session_id": "abc123",
  "mode": "interview",
  "ai_provider": "claude",
  "stt_provider": "deepgram"
}
```

### session.stopped
```json
{
  "session_id": "abc123",
  "duration_seconds": 1800
}
```

### session.state_changed
```json
{
  "previous": "LISTENING",
  "current": "QUESTION_DETECTED"
}
```

---

## Audio Events

### audio.started
```json
{ "device_id": "...", "source": "system" }
```

### audio.stopped
```json
{ "reason": "user_action" }
```

### audio.error
```json
{ "code": "DEVICE_NOT_FOUND", "message": "..." }
```

### audio.vad_state_changed
```json
{ "state": "SPEAKING" }
```

---

## Speech Events

### speech.partial
```json
{
  "speaker": "other",
  "text": "How did you implement..."
}
```

### speech.final
```json
{
  "speaker": "other",
  "text": "How did you implement your RAG system?",
  "confidence": 0.97
}
```

---

## Question Events

### question.detected
```json
{
  "question_id": "q_abc",
  "question": "How did you implement your RAG system?",
  "category": "technical",
  "confidence": 0.95,
  "is_followup": false
}
```

### question.completed
```json
{
  "question_id": "q_abc",
  "resolved_question": "How did you implement your RAG system?"
}
```

---

## Context Events

### context.search.started
```json
{ "question_id": "q_abc" }
```

### context.search.completed
```json
{
  "question_id": "q_abc",
  "sources": ["Resume", "RAG Project"],
  "chunk_count": 5,
  "latency_ms": 87
}
```

---

## AI Events

### ai.request.started
```json
{
  "question_id": "q_abc",
  "provider": "claude",
  "model": "claude-3-5-sonnet-20241022"
}
```

### ai.token
```json
{
  "question_id": "q_abc",
  "token": "I"
}
```

### ai.completed
```json
{
  "question_id": "q_abc",
  "answer": "...",
  "tokens_used": 312,
  "latency_ms": 1240,
  "ttft_ms": 640
}
```

### ai.error
```json
{
  "question_id": "q_abc",
  "code": "RATE_LIMITED",
  "message": "...",
  "retry_after_ms": 5000
}
```

### ai.cancelled
```json
{
  "question_id": "q_abc",
  "reason": "new_question"
}
```

---

## Overlay Events

### overlay.show
```json
{}
```

### overlay.hide
```json
{}
```

### overlay.clickthrough_changed
```json
{ "enabled": true }
```

### overlay.opacity_changed
```json
{ "opacity": 0.85 }
```

---

## Document Events

### document.ingestion.started
```json
{ "document_id": "doc_abc", "name": "resume.pdf", "type": "pdf" }
```

### document.ingestion.progress
```json
{ "document_id": "doc_abc", "progress": 0.72, "stage": "embedding" }
```

### document.ingestion.completed
```json
{ "document_id": "doc_abc", "chunks": 42, "latency_ms": 3400 }
```

### document.ingestion.failed
```json
{ "document_id": "doc_abc", "error": "PDF_PARSE_ERROR", "message": "..." }
```

---

## Error Events

### error.recoverable
```json
{ "code": "STT_CONNECTION_LOST", "message": "...", "will_retry": true }
```

### error.fatal
```json
{ "code": "AUDIO_DEVICE_MISSING", "message": "..." }
```

---

## Directionality

- **Python -> Electron**: All events above
- **Electron -> Python**: Commands

### Commands (Electron -> Python)

```json
{ "type": "command.start_listening", "payload": { "source": "system" } }
{ "type": "command.stop_listening", "payload": {} }
{ "type": "command.regenerate", "payload": { "question_id": "q_abc" } }
{ "type": "command.cancel", "payload": { "question_id": "q_abc" } }
{ "type": "command.set_mode", "payload": { "mode": "technical" } }
{ "type": "command.take_screenshot", "payload": {} }
```
