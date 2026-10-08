"""
Client-side Device Identity & Hardware Profiler for Systems Under Test (SUT).
Generates a persistent UUID and collects non-invasive hardware metrics.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import platform
import socket
import uuid
import psutil

from app.logging.logger import get_logger

logger = get_logger(__name__)

CONFIG_DIR = Path.home() / ".ai-teleprompter"
IDENTITY_FILE = CONFIG_DIR / "device_identity.json"


def get_or_create_device_id() -> str:
    """Read or generate persistent unique device identifier (e.g. SUT-XXXXXXXX)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if IDENTITY_FILE.exists():
        try:
            with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("device_id"):
                    return data["device_id"]
        except Exception as e:
            logger.warning("Could not read identity file", error=str(e))

    # Generate persistent SUT ID
    short_uuid = uuid.uuid4().hex[:8].upper()
    device_id = f"SUT-{short_uuid}"

    identity_data = {
        "device_id": device_id,
        "device_token": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identity_data, f, indent=2)

    logger.info("Generated new persistent device identity", device_id=device_id)
    return device_id


def save_device_token(token: str) -> None:
    """Save persistent authenticated device token."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    identity_data = {}
    if IDENTITY_FILE.exists():
        try:
            with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
                identity_data = json.load(f)
        except Exception:
            pass

    identity_data["device_token"] = token
    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identity_data, f, indent=2)


def get_device_token() -> str:
    """Retrieve saved device token."""
    if IDENTITY_FILE.exists():
        try:
            with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("device_token", "")
        except Exception:
            pass
    return ""


def collect_system_profile(app_version: str = "0.1.0", agent_version: str = "1.0.0") -> dict:
    """Collect hardware specifications without personal private data."""
    try:
        cpu_name = platform.processor() or f"{psutil.cpu_count(logical=True)} Core CPU"
    except Exception:
        cpu_name = "x86_64 Processor"

    try:
        mem = psutil.virtual_memory()
        ram_gb = f"{round(mem.total / (1024**3))} GB"
    except Exception:
        ram_gb = "8 GB"

    try:
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        disk_str = f"{round(disk.free / (1024**3))} GB free / {round(disk.total / (1024**3))} GB"
    except Exception:
        disk_str = "Unknown"

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    device_id = get_or_create_device_id()

    return {
        "device_id": device_id,
        "hostname": platform.node() or "TEST-SYSTEM",
        "os": platform.system() or "Windows",
        "os_version": f"{platform.system()} {platform.release()} ({platform.version()[:15]})",
        "cpu": cpu_name,
        "ram": ram_gb,
        "disk_space": disk_str,
        "ip_address": local_ip,
        "python_version": platform.python_version(),
        "application_version": app_version,
        "agent_version": agent_version,
    }
