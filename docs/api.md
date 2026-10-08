# AI Teleprompter — API Reference

## Base URL

```
http://127.0.0.1:8765/api/v1
```

## Authentication

All requests require a bearer token in the Authorization header:
```
Authorization: Bearer <startup_token>
```

The token is generated on backend startup and passed to Electron via stdout or environment.

---

## Health

### GET /health

Returns backend health status.

**Response**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "components": {
    "database": "ok",
    "audio": "ok",
    "stt": "disconnected",
    "ai": "ok"
  }
}
```

---

## Settings

### GET /settings

Returns all current settings.

**Response**:
```json
{
  "general": {
    "start_with_os": false,
    "start_minimized": false,
    "default_mode": "interview",
    "auto_start_listening": false
  },
  "audio": {
    "source": "system",
    "device_id": null,
    "vad_enabled": true,
    "vad_sensitivity": 0.5
  },
  "ai": {
    "provider": "claude",
    "model": "claude-3-5-sonnet-20241022",
    "temperature": 0.7,
    "max_tokens": 500
  },
  "appearance": {
    "opacity": 0.85,
    "font_size": 14,
    "theme": "dark",
    "width": 420,
    "max_answer_height": 400,
    "show_question": true,
    "show_sources": true
  },
  "privacy": {
    "save_transcripts": false,
    "save_audio": false,
    "local_only_mode": false
  }
}
```

### PUT /settings

Updates settings (partial update supported).

**Request body**: Partial settings object.
**Response**: Updated settings object.

---

## Sessions

### POST /sessions

Create a new session.

**Request**:
```json
{
  "mode": "interview",
  "ai_provider": "claude",
  "stt_provider": "deepgram"
}
```

**Response**:
```json
{
  "session_id": "abc123",
  "created_at": "2024-01-01T00:00:00Z",
  "status": "active"
}
```

### GET /sessions/{session_id}

Get session details.

### PUT /sessions/{session_id}/stop

Stop an active session.

---

## Documents

### POST /documents

Ingest a document.

**Request** (multipart/form-data):
- `file`: The document file
- `name`: Display name
- `type`: `pdf` | `txt` | `md` | `code` | `docx`
- `tags`: Comma-separated tags

**Response**:
```json
{
  "document_id": "doc_abc",
  "status": "processing"
}
```

### GET /documents

List all documents.

### DELETE /documents/{document_id}

Remove a document and its chunks from the vector store.

---

## Devices

### GET /audio/devices

List available audio devices.

**Response**:
```json
{
  "devices": [
    {
      "id": "...",
      "name": "Speakers (Realtek)",
      "type": "output",
      "is_loopback": true,
      "is_default": true
    }
  ]
}
```

---

## WebSocket

### WS /ws/events

Bidirectional event stream.

**Connection**: `ws://127.0.0.1:8765/ws/events?token=<startup_token>`

See [events.md](./events.md) for full event catalog.
