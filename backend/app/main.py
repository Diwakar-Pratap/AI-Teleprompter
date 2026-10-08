"""
FastAPI application factory.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.api.websocket import ws_router
from app.logging.logger import get_logger
from app.database.engine import init_db
from app.settings.manager import SettingsManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    logger.info("AI Teleprompter backend starting...")

    # Initialize database and run migrations
    await init_db()
    logger.info("Database initialized")

    # Initialize settings
    settings_manager = SettingsManager()
    await settings_manager.initialize()
    app.state.settings_manager = settings_manager
    logger.info("Settings loaded")

    # Pre-warm speech-to-text engines so they are instant upon first speech
    try:
        from app.stt.transcriber import get_transcriber
        get_transcriber()
    except Exception as e:
        logger.warning("Could not pre-warm STT model on startup", error=str(e))

    # Initialize OTA defaults (settings and versions catalog)
    try:
        import os
        from app.database.engine import AsyncSessionLocal
        from app.ota.settings_service import init_default_settings
        from app.ota.ota_service import init_default_versions
        from app.ota.agent.heartbeat_client import HeartbeatAgent

        async with AsyncSessionLocal() as session:
            await init_default_settings(session)
            await init_default_versions(session)

        if os.getenv("TESTING") != "1":
            server_url = os.getenv("OTA_SERVER_URL", os.getenv("CENTRAL_SERVER_URL", "http://127.0.0.1:8765"))
            interval = int(os.getenv("OTA_HEARTBEAT_INTERVAL", "30"))
            heartbeat_agent = HeartbeatAgent(
                server_url=server_url,
                interval_seconds=interval,
                app_version="0.1.0",
                agent_version="1.0.0",
            )
            await heartbeat_agent.start()
            app.state.heartbeat_agent = heartbeat_agent
    except Exception as e:
        logger.warning("Could not initialize OTA subsystems", error=str(e))

    print("Application startup complete", flush=True)
    logger.info("Backend ready")

    yield

    # Shutdown
    if hasattr(app.state, "heartbeat_agent"):
        try:
            await app.state.heartbeat_agent.stop()
        except Exception:
            pass

    logger.info("Backend shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Teleprompter API",
        version="0.1.0",
        description="Backend API for AI Teleprompter",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # CORS — allow all local origins and Electron file://
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root_status():
        return {
            "status": "online",
            "service": "AI Teleprompter Backend",
            "health": "/health",
            "api_health": "/api/v1/health",
            "docs": "/docs",
            "ws": "/ws/events",
        }

    @app.get("/health")
    async def direct_health():
        from app.api.routes import health_check
        return await health_check()

    @app.post("/shutdown")
    async def direct_shutdown():
        import asyncio
        import os
        logger.info("Direct shutdown requested via /shutdown")
        asyncio.get_event_loop().call_later(0.1, os._exit, 0)
        return {"status": "shutting_down"}

    # Register routers
    from app.api.ota_routes import ota_router
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(ota_router, prefix="/api/v1")
    app.include_router(ws_router)

    from fastapi.responses import FileResponse
    from pathlib import Path

    dashboard_file = Path(__file__).parent / "static" / "admin" / "index.html"

    @app.get("/admin", response_class=FileResponse)
    @app.get("/dashboard", response_class=FileResponse)
    async def serve_admin_dashboard():
        if dashboard_file.exists():
            return FileResponse(dashboard_file)
        return JSONResponse({"status": "dashboard_missing", "path": str(dashboard_file)}, status_code=404)

    return app
