# AI Teleprompter

Transparent desktop AI assistant overlay built with Electron, React, TypeScript, Tailwind CSS, FastAPI, and SQLite.

## Overview

AI Teleprompter is designed to capture permitted system audio/microphone, transcribe speech in real-time, detect and classify questions, retrieve relevant personal context (resumes, projects, docs), and display concise answers in an always-on-top transparent desktop overlay.

---

## Phase 1 Status: Foundation Complete

- **Electron + React + TypeScript + Tailwind CSS**
- **Vite** build pipeline via `electron-vite`
- **Transparent, frameless, always-on-top** overlay window
- **Click-through mode** toggling (`Ctrl+Shift+M`)
- **Configurable opacity** and positioning
- **Global shortcuts** (`ShortcutManager`)
- **System tray** integration with context menu (`TrayManager`)
- **FastAPI backend** (`127.0.0.1:8765`)
- **WebSocket connection** (`/ws/events`) for live bidirectional streaming
- **Health check & Settings REST endpoints**
- **Zustand state management** for reactive UI
- **Automated test suite**: 14 tests passing (`pytest`)
- **TypeScript strict type checking**: zero errors

---

## Architecture & Documentation

Comprehensive system specifications are available in the [`docs/`](./docs) directory:
- [Architecture](docs/architecture.md)
- [Technical Decisions](docs/technical-decisions.md)
- [Development Plan](docs/development-plan.md)
- [API Reference](docs/api.md)
- [Event System](docs/events.md)

---

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- npm 10+
- Windows 10/11

### Setup

Run the automated setup script:

```powershell
.\scripts\setup.ps1
```

Or manually:

```powershell
# Install frontend dependencies
npm install

# Setup backend environment
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
cd ..

# Copy environment template
cp .env.example .env
```

### Running in Development

```powershell
# Run backend and frontend together
.\scripts\dev.ps1
```

Or run services individually:

1. **Backend**:
   ```powershell
   python backend/main.py --host 127.0.0.1 --port 8765
   ```
2. **Desktop (Electron)**:
   ```powershell
   npm run dev
   ```

### Running Tests

```powershell
.\scripts\test.ps1
```

---

## Keyboard Shortcuts

- `Ctrl+Shift+Space`: Show / Hide Overlay
- `Ctrl+Shift+L`: Start / Stop Listening
- `Ctrl+Shift+P`: Command Palette
- `Ctrl+Shift+K`: Context Library
- `Ctrl+Shift+X`: Screen capture
- `Ctrl+Shift+R`: Regenerate answer
- `Ctrl+Shift+S`: Short answer mode
- `Ctrl+Shift+T`: Technical answer mode
- `Ctrl+Shift+C`: Clear answer
- `Ctrl+Shift+M`: Toggle click-through mode
