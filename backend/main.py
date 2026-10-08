"""
AI Teleprompter — Python Backend Entry Point

Starts the FastAPI application with uvicorn.
Accepts --host and --port arguments from the command line.
"""

import argparse
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Teleprompter Backend")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Set environment variables before importing app
    os.environ["BACKEND_HOST"] = args.host
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
