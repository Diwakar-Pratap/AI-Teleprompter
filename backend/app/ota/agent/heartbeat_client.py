"""
Client-side Heartbeat Worker & OTA Job Dispatcher.
Maintains device presence, syncs limits, and dispatches remote OTA update commands.
"""

import asyncio
from datetime import datetime
from typing import Optional, Callable, Dict, Any
import httpx

from app.ota.agent.identity import collect_system_profile, get_or_create_device_id, get_device_token, save_device_token
from app.ota.agent.updater import OTAUpdater
from app.logging.logger import get_logger

logger = get_logger(__name__)


class HeartbeatAgent:
    """Async background worker for SUT presence and remote OTA execution."""

    def __init__(
        self,
        server_url: str = "https://salvaging-quiver-preheated.ngrok-free.dev",
        interval_seconds: int = 60,
        app_version: str = "0.1.0",
        agent_version: str = "1.0.0",
        on_license_change: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.interval_seconds = interval_seconds
        self.app_version = app_version
        self.agent_version = agent_version
        self.on_license_change = on_license_change
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.updater = OTAUpdater(server_url=self.server_url)

    async def register_device(self) -> bool:
        """Register or update device information with backend."""
        profile = collect_system_profile(app_version=self.app_version, agent_version=self.agent_version)
        try:
            headers = {"ngrok-skip-browser-warning": "69420", "User-Agent": "AITeleprompter/1.0"}
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                resp = await client.post(f"{self.server_url}/api/v1/devices/register", json=profile)
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("device_token")
                    if token:
                        save_device_token(token)
                    logger.info("Device registered with backend", device_id=profile["device_id"])
                    return True
        except Exception as e:
            logger.warning("Could not register device with backend (may be starting up)", error=str(e))
        return False

    async def send_heartbeat(self, usage_count: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Send a single heartbeat pulse to backend."""
        device_id = get_or_create_device_id()
        device_token = get_device_token()
        if not device_token:
            await self.register_device()
            device_token = get_device_token()

        try:
            headers = {"ngrok-skip-browser-warning": "69420", "User-Agent": "AITeleprompter/1.0"}
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                resp = await client.post(
                    f"{self.server_url}/api/v1/devices/heartbeat",
                    json={
                        "device_id": device_id,
                        "device_token": device_token,
                        "app_version": self.app_version,
                        "agent_version": self.agent_version,
                        "usage_count": usage_count,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()


                    # Check for pending OTA job
                    pending_job = data.get("pending_ota_job")
                    if pending_job:
                        logger.info("Received remote OTA command!", job=pending_job)
                        asyncio.create_task(
                            self.updater.execute_job(
                                job=pending_job,
                                device_id=device_id,
                                device_token=device_token,
                            )
                        )

                    # Notify license listener if state changed
                    if self.on_license_change:
                        self.on_license_change(data)

                    return data
        except Exception as e:
            logger.debug("Heartbeat ping skipped", error=str(e))
        return None

    async def start(self) -> None:
        """Start the periodic heartbeat loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("OTA Heartbeat Agent started", interval=self.interval_seconds)

    async def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OTA Heartbeat Agent stopped")

    async def _loop(self) -> None:
        """Periodic background execution loop."""
        # Initial registration attempt
        await self.register_device()
        await self.send_heartbeat()

        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                if self._running:
                    await self.send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat loop error", error=str(e))
                await asyncio.sleep(5)
