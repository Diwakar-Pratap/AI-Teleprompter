"""
Phase 1 Backend Tests

Tests for:
- Health endpoint
- Settings endpoints
- Sessions endpoints
- WebSocket connection
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json


@pytest.fixture
def app() -> FastAPI:
    """Create test app instance."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    import os
    os.environ["TESTING"] = "1"

    from app.main import create_app
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app, raise_server_exceptions=True)


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data
        assert "components" in data

    def test_health_has_component_keys(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        data = response.json()
        components = data["components"]
        assert "database" in components


class TestSettings:
    def test_get_settings_returns_defaults(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert "general" in data
        assert "audio" in data
        assert "ai" in data
        assert "appearance" in data
        assert "privacy" in data

    def test_get_settings_default_values(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        data = response.json()
        assert data["appearance"]["opacity"] == 0.95
        assert data["ai"]["provider"] in ["claude", "nvidia"]
        assert data["privacy"]["save_transcripts"] is False

    def test_update_settings(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/settings",
            json={"appearance": {"opacity": 0.7}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["appearance"]["opacity"] == 0.7

    def test_update_settings_partial(self, client: TestClient) -> None:
        """Partial update should not affect other fields."""
        response = client.put(
            "/api/v1/settings",
            json={"general": {"start_with_os": True}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["general"]["start_with_os"] is True
        assert data["ai"]["provider"] in ["claude", "nvidia"]


class TestSessions:
    def test_create_session(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/sessions",
            json={"mode": "interview", "ai_provider": "claude"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "active"
        assert data["mode"] == "interview"

    def test_get_session(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/v1/sessions",
            json={"mode": "technical"},
        )
        session_id = create_resp.json()["session_id"]

        get_resp = client.get(f"/api/v1/sessions/{session_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["session_id"] == session_id

    def test_get_nonexistent_session_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/sessions/nonexistent-id")
        assert response.status_code == 404

    def test_stop_session(self, client: TestClient) -> None:
        create_resp = client.post("/api/v1/sessions", json={"mode": "interview"})
        session_id = create_resp.json()["session_id"]

        stop_resp = client.put(f"/api/v1/sessions/{session_id}/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "stopped"


class TestWebSocket:
    def test_websocket_connects_and_receives_welcome(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/events") as ws:
            data = ws.receive_text()
            event = json.loads(data)
            assert event["type"] == "connection.established"
            assert "id" in event
            assert "timestamp" in event

    def test_websocket_handles_invalid_json(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/events") as ws:
            # Drain connection.established and any license.blocked events
            for _ in range(3):
                data = ws.receive_text()
                event = json.loads(data)
                if event["type"] == "connection.established":
                    break
            ws.send_text("not json at all")
            # Drain any license.blocked emitted before error.recoverable
            for _ in range(3):
                response = ws.receive_text()
                event = json.loads(response)
                if event["type"] == "error.recoverable":
                    break
            assert event["type"] == "error.recoverable"
            assert event["payload"]["code"] == "INVALID_JSON"

    def test_websocket_handles_toggle_listening_command(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/events") as ws:
            # Drain connection.established and any license.blocked events
            for _ in range(3):
                data = ws.receive_text()
                event = json.loads(data)
                if event["type"] == "connection.established":
                    break
            ws.send_text(json.dumps({
                "type": "command.toggle_listening",
                "payload": {},
                "timestamp": "2024-01-01T00:00:00Z",
            }))
            # Drain license.blocked if device is blocked, or accept session.state_changed / audio.started
            for _ in range(3):
                response = ws.receive_text()
                event = json.loads(response)
                if event["type"] in ("session.state_changed", "audio.started", "license.blocked"):
                    break
            assert event["type"] in ("session.state_changed", "audio.started", "license.blocked")

    def test_websocket_event_has_required_fields(self, client: TestClient) -> None:
        with client.websocket_connect("/ws/events") as ws:
            data = ws.receive_text()
            event = json.loads(data)
            assert "id" in event
            assert "type" in event
            assert "timestamp" in event
            assert "payload" in event
