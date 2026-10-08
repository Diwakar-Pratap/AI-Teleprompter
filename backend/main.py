"""
AI Teleprompter — Python Backend Entry Point

Starts the FastAPI application with uvicorn.
Accepts --host and --port arguments from the command line or environment variables.
"""

import argparse
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Patch sqlite3 with pysqlite3-binary if built-in _sqlite3 is missing on custom Linux builds
try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except (ImportError, KeyError):
    pass


def parse_args() -> argparse.Namespace:
    env_port_str = os.getenv("PORT", os.getenv("BACKEND_PORT", "8765"))
    try:
        env_port = int(env_port_str)
    except (ValueError, TypeError):
        env_port = 8765

    # If PORT is in environment (cloud deploy), default host to 0.0.0.0
    default_host = "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"
    env_host = os.getenv("HOST", os.getenv("BACKEND_HOST", default_host))

    parser = argparse.ArgumentParser(description="AI Teleprompter Backend")
    parser.add_argument("--host", default=env_host, help="Host to bind to")
    parser.add_argument("--port", default=env_port, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")

    # Clean argv to tolerate empty parameters from cloud shells (e.g. --port $PORT when $PORT is unset)
    clean_argv = []
    i = 1
    raw_argv = sys.argv
    while i < len(raw_argv):
        arg = raw_argv[i]
        if arg in ("--port", "-p"):
            if i + 1 < len(raw_argv) and not raw_argv[i + 1].startswith("-") and raw_argv[i + 1].strip():
                clean_argv.extend([arg, raw_argv[i + 1].strip()])
                i += 2
            else:
                clean_argv.extend([arg, str(env_port)])
                i += 1
        elif arg in ("--host",):
            if i + 1 < len(raw_argv) and not raw_argv[i + 1].startswith("-") and raw_argv[i + 1].strip():
                clean_argv.extend([arg, raw_argv[i + 1].strip()])
                i += 2
            else:
                clean_argv.extend([arg, env_host])
                i += 1
        else:
            clean_argv.append(arg)
            i += 1

    parsed = parser.parse_args(clean_argv)
    try:
        parsed.port = int(parsed.port)
    except (ValueError, TypeError):
        parsed.port = env_port

    return parsed


def main() -> None:
    args = parse_args()

    # Set environment variables before importing app
    os.environ["BACKEND_HOST"] = str(args.host)
    os.environ["BACKEND_PORT"] = str(args.port)

    import uvicorn

    print(f"AI Teleprompter Backend starting on {args.host}:{args.port}", flush=True)

    if args.reload:
        uvicorn.run(
            "app.main:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            access_log=False,
            reload=True,
        )
    else:
        from app.main import create_app
        app = create_app()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            access_log=False,
            reload=False,
        )


if __name__ == "__main__":
    main()
