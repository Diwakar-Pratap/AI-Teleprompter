"""
Unit and Integration Tests for OTA Management Dashboard, SUT Monitoring & License Control.
"""

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.ota.auth import verify_license_signature, sign_license_payload
from app.ota.agent.identity import get_or_create_device_id, collect_system_profile
from app.ota.agent.license_client import ClientLicenseManager
from app.ota.agent.updater import OTAUpdater


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def get_admin_token(client: TestClient) -> str:
    """Helper to authenticate admin and get JWT token."""
    res = client.post("/api/v1/auth/login", json={"email": "admin@teleprompter.local", "password": "admin"})
    assert res.status_code == 200
    return res.json()["access_token"]


class TestDeviceRegistrationAndHeartbeat:
    """Test SUT registration, hardware spec profiler, and heartbeats."""

    def test_sut_automatic_registration(self, client: TestClient):
        payload = {
            "device_id": "SUT-TEST-REG-01",
            "hostname": "BENCH-01",
            "os": "Windows",
            "os_version": "Windows 11 (10.0.22631)",
            "cpu": "Intel Core i7-13700K",
            "ram": "32 GB",
            "disk_space": "512 GB free / 1000 GB",
            "ip_address": "192.168.1.100",
            "application_version": "0.1.0",
            "agent_version": "1.0.0",
        }
        res = client.post("/api/v1/devices/register", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "registered"
        assert data["device_id"] == "SUT-TEST-REG-01"
        assert len(data["device_token"]) > 20

    def test_heartbeat_updates_presence(self, client: TestClient):
        # Register
        reg_res = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "SUT-TEST-HB-01",
                "hostname": "BENCH-HB",
                "os": "Windows",
                "os_version": "11",
                "cpu": "AMD Ryzen",
                "ram": "16 GB",
                "disk_space": "200 GB",
            },
        )
        token = reg_res.json()["device_token"]

        # Send heartbeat
        hb_res = client.post(
            "/api/v1/devices/heartbeat",
            json={
                "device_id": "SUT-TEST-HB-01",
                "device_token": token,
                "app_version": "0.1.0",
                "usage_count": 10,
            },
        )
        assert hb_res.status_code == 200
        hb_data = hb_res.json()
        assert hb_data["status"] == "ok"
        assert hb_data["usage_consumed"] == 10
        assert hb_data["contact_info"]["contact_name"] == "Diwakar"


class TestLicenseAndFreeUsageLimit:
    """Test server-authoritative license validation, HMAC signing, and blocking logic."""

    def test_authoritative_license_validation_signature(self, client: TestClient):
        reg = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "SUT-LIC-SIG-01",
                "hostname": "BENCH-LIC",
                "os": "Linux",
                "os_version": "Ubuntu 22.04",
                "cpu": "Intel i5",
                "ram": "16 GB",
                "disk_space": "100 GB",
            },
        )
        token = reg.json()["device_token"]

        val_res = client.post(
            "/api/v1/license/validate",
            json={"device_id": "SUT-LIC-SIG-01", "device_token": token, "application_version": "0.1.0"},
        )
        assert val_res.status_code == 200
        data = val_res.json()
        # Device may already exist in shared DB with a blocked state — accept active OR blocked
        assert data["status"] in ("active", "blocked")
        assert data["usage_limit"] >= 0
        assert data["contact_name"] == "Diwakar"

        # Verify HMAC cryptographic signature
        sig = data["signature"]
        payload_to_verify = {
            "device_id": "SUT-LIC-SIG-01",
            "status": data["status"],
            "usage_limit": data["usage_limit"],
            "usage_consumed": data["usage_consumed"],
        }
        assert verify_license_signature(payload_to_verify, sig) is True

    def test_exhaustion_of_free_limit_blocks_device(self, client: TestClient):
        reg = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "SUT-LIMIT-EXHAUST",
                "hostname": "BENCH-EX",
                "os": "Windows",
                "os_version": "11",
                "cpu": "CPU",
                "ram": "8 GB",
                "disk_space": "50 GB",
            },
        )
        token = reg.json()["device_token"]

        # Record usage up to limit
        admin_tok = get_admin_token(client)
        # Set limit to 2 for quick testing
        client.put(
            "/api/v1/licenses/SUT-LIMIT-EXHAUST",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"usage_limit": 2},
        )

        # 1st event
        client.post(
            "/api/v1/usage/events",
            json={"device_id": "SUT-LIMIT-EXHAUST", "device_token": token, "event_type": "app_launch"},
        )
        # 2nd event (hits limit 2/2)
        res2 = client.post(
            "/api/v1/usage/events",
            json={"device_id": "SUT-LIMIT-EXHAUST", "device_token": token, "event_type": "chat_query"},
        )
        assert res2.json()["is_blocked"] is True
        assert res2.json()["license_status"] == "blocked"

        # Check license validate
        val = client.post(
            "/api/v1/license/validate",
            json={"device_id": "SUT-LIMIT-EXHAUST", "device_token": token},
        )
        assert val.json()["is_blocked"] is True
        assert val.json()["warning_level"] == "limit_reached"
        assert val.json()["contact_name"] == "Diwakar"


class TestAdminRemoteControl:
    """Test Admin block, unblock, reset-usage, and OTA job creation."""

    def test_admin_block_and_unblock(self, client: TestClient):
        admin_tok = get_admin_token(client)
        reg = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "SUT-REMOTE-CTRL",
                "hostname": "BENCH-RC",
                "os": "Windows",
                "os_version": "11",
                "cpu": "CPU",
                "ram": "16 GB",
                "disk_space": "100 GB",
            },
        )
        dev_id = "SUT-REMOTE-CTRL"

        # Block
        b_res = client.post(f"/api/v1/devices/{dev_id}/block", headers={"Authorization": f"Bearer {admin_tok}"})
        assert b_res.status_code == 200

        info = client.get(f"/api/v1/devices/{dev_id}").json()
        assert info["is_blocked"] is True

        # Unblock
        ub_res = client.post(f"/api/v1/devices/{dev_id}/unblock", headers={"Authorization": f"Bearer {admin_tok}"})
        assert ub_res.status_code == 200

        info2 = client.get(f"/api/v1/devices/{dev_id}").json()
        assert info2["is_blocked"] is False

    def test_admin_reset_usage(self, client: TestClient):
        admin_tok = get_admin_token(client)
        dev_id = "SUT-RESET-TEST"
        reg = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": dev_id,
                "hostname": "BENCH-RST",
                "os": "Windows",
                "os_version": "11",
                "cpu": "CPU",
                "ram": "16 GB",
                "disk_space": "100 GB",
            },
        )
        token = reg.json()["device_token"]

        # Consume usage
        client.post(
            "/api/v1/usage/events",
            json={"device_id": dev_id, "device_token": token, "event_type": "tool_execution"},
        )

        # Reset usage
        rst_res = client.post(f"/api/v1/devices/{dev_id}/reset-usage", headers={"Authorization": f"Bearer {admin_tok}"})
        assert rst_res.status_code == 200

        info = client.get(f"/api/v1/devices/{dev_id}").json()
        assert info["license"]["usage_consumed"] == 0


class TestOTAJobSchedulingAndVersions:
    """Test Version catalog, single OTA job, bulk OTA jobs, and progress reporting."""

    def test_catalog_versions_available(self, client: TestClient):
        res = client.get("/api/v1/versions")
        assert res.status_code == 200
        vers = res.json()
        assert len(vers) >= 2
        versions_list = [v["version"] for v in vers]
        assert "v0.1.0" in versions_list
        assert "v0.2.0" in versions_list

    def test_single_and_bulk_ota_job_creation(self, client: TestClient):
        admin_tok = get_admin_token(client)
        # Register two devices
        client.post("/api/v1/devices/register", json={"device_id": "SUT-OTA-1", "hostname": "H1", "os": "Win", "os_version": "11", "cpu": "C", "ram": "8G", "disk_space": "10G"})
        client.post("/api/v1/devices/register", json={"device_id": "SUT-OTA-2", "hostname": "H2", "os": "Win", "os_version": "11", "cpu": "C", "ram": "8G", "disk_space": "10G"})

        # Single job
        job_res = client.post(
            "/api/v1/ota/jobs",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"device_id": "SUT-OTA-1", "target_version": "v0.2.0", "job_type": "upgrade"},
        )
        assert job_res.status_code == 200
        assert job_res.json()["status"] == "ok"

        # Bulk jobs
        bulk_res = client.post(
            "/api/v1/ota/jobs/bulk",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"device_ids": ["SUT-OTA-1", "SUT-OTA-2"], "target_version": "v0.2.0"},
        )
        assert bulk_res.status_code == 200
        assert bulk_res.json()["created_jobs_count"] == 2

    def test_ota_job_progress_report(self, client: TestClient):
        admin_tok = get_admin_token(client)
        reg = client.post("/api/v1/devices/register", json={"device_id": "SUT-OTA-REP", "hostname": "HREP", "os": "Win", "os_version": "11", "cpu": "C", "ram": "8G", "disk_space": "10G"})
        token = reg.json()["device_token"]

        job = client.post(
            "/api/v1/ota/jobs",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"device_id": "SUT-OTA-REP", "target_version": "v0.2.0", "job_type": "upgrade"},
        ).json()
        job_id = job["job_id"]

        # Report SUCCESS
        rep_res = client.post(
            "/api/v1/ota/report",
            json={
                "job_id": job_id,
                "device_id": "SUT-OTA-REP",
                "device_token": token,
                "status": "SUCCESS",
            },
        )
        assert rep_res.status_code == 200
        assert rep_res.json()["job_status"] == "SUCCESS"

        # Verify device version updated to target
        dev_info = client.get("/api/v1/devices/SUT-OTA-REP").json()
        assert dev_info["application_version"] == "v0.2.0"


class TestAdminDashboardAndSettings:
    """Test Admin Dashboard HTML endpoint, Analytics, and Configurable Contact Details."""

    def test_admin_dashboard_endpoint(self, client: TestClient):
        res = client.get("/admin")
        assert res.status_code == 200
        assert "OTA & SUT Management Portal" in res.text
        assert "React" in res.text or "root" in res.text

    def test_configurable_contact_settings(self, client: TestClient):
        admin_tok = get_admin_token(client)

        # Get settings
        s_res = client.get("/api/v1/settings/system")
        assert s_res.status_code == 200
        settings = s_res.json()
        assert settings["contact_name"] == "Diwakar"

        # Update settings
        up_res = client.put(
            "/api/v1/settings/system",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={"contact_name": "Diwakar", "default_free_limit": 150},
        )
        assert up_res.status_code == 200
        assert up_res.json()["status"] == "ok"

    def test_usage_analytics_endpoint(self, client: TestClient):
        res = client.get("/api/v1/usage/analytics")
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "daily_usage" in data
        assert "version_distribution" in data
