import {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  Menu,
  Tray,
  nativeImage,
  screen,
  shell,
} from "electron";
import { join } from "path";
import { existsSync } from "fs";
import { spawn, ChildProcess } from "child_process";
import { WindowManager } from "./windows/WindowManager";
import { ShortcutManager } from "./shortcuts/ShortcutManager";
import { TrayManager } from "./tray/TrayManager";
import { IPCManager } from "./ipc/IPCManager";
import { SecurityManager } from "./security/SecurityManager";

let windowManager: WindowManager;
let shortcutManager: ShortcutManager;
let trayManager: TrayManager;
let ipcManager: IPCManager;
let securityManager: SecurityManager;
let backendProcess: ChildProcess | null = null;
let backendReady = false;

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = 8765;

/**
 * Check if the backend is already running (e.g. launched via start.bat).
 */
async function checkBackendRunning(): Promise<boolean> {
  try {
    const response = await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Start the Python FastAPI backend process if not already running.
 */
async function startBackend(): Promise<void> {
  const isAlreadyRunning = await checkBackendRunning();
  if (isAlreadyRunning) {
    console.log("[Main] Backend is already running on port", BACKEND_PORT);
    backendReady = true;
    return;
  }

  const getPythonPath = (): string => {
    if (app.isPackaged) {
      const bundledCandidates = [
        join(process.resourcesPath, "python", "pythonw.exe"),
        join(process.resourcesPath, "python", "python.exe"),
        join(process.resourcesPath, "app.asar.unpacked", "python", "pythonw.exe"),
        join(process.resourcesPath, "app.asar.unpacked", "python", "python.exe"),
      ];
      for (const b of bundledCandidates) {
        if (existsSync(b)) return b;
      }
    }
    const localAppData = process.env.LOCALAPPDATA || "";
    const programFiles = process.env.ProgramFiles || "C:\\Program Files";
    const candidates = [
      join(localAppData, "Programs", "Python", "Python311", "pythonw.exe"),
      join(localAppData, "Programs", "Python", "Python311", "python.exe"),
      join(localAppData, "Programs", "Python", "Python312", "pythonw.exe"),
      join(localAppData, "Programs", "Python", "Python312", "python.exe"),
      join(localAppData, "Programs", "Python", "Python310", "pythonw.exe"),
      join(localAppData, "Programs", "Python", "Python310", "python.exe"),
      join(localAppData, "Programs", "Python", "Python313", "pythonw.exe"),
      join(localAppData, "Programs", "Python", "Python313", "python.exe"),
      join(programFiles, "Python311", "pythonw.exe"),
      join(programFiles, "Python311", "python.exe"),
      join(programFiles, "Python312", "pythonw.exe"),
      join(programFiles, "Python312", "python.exe"),
      "C:\\Python311\\pythonw.exe",
      "C:\\Python311\\python.exe",
      "C:\\Python312\\pythonw.exe",
      "C:\\Python312\\python.exe",
      "pythonw",
      "python",
    ];
    for (const c of candidates) {
      if (c.includes("\\") && existsSync(c)) {
        return c;
      }
    }
    return "python";
  };

  const isDev = !app.isPackaged;
  const pythonPath = getPythonPath();
  const backendDir = isDev
    ? join(__dirname, "../../backend")
    : existsSync(join(process.resourcesPath, "backend"))
    ? join(process.resourcesPath, "backend")
    : existsSync(join(process.resourcesPath, "app.asar.unpacked", "backend"))
    ? join(process.resourcesPath, "app.asar.unpacked", "backend")
    : join(__dirname, "../../backend");
  const scriptPath = join(backendDir, "main.py");

  console.log("[Main] Starting Python backend from:", backendDir, "using:", pythonPath);

  backendProcess = spawn(pythonPath, [scriptPath, "--host", BACKEND_HOST, "--port", String(BACKEND_PORT)], {
    cwd: backendDir,
    env: {
      ...process.env,
      BACKEND_HOST,
      BACKEND_PORT: String(BACKEND_PORT),
    },
    windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
  });

  backendProcess.on("error", (err) => {
    console.error("[Main] Backend process spawn error:", err);
  });

  backendProcess.stdout?.on("data", (data: Buffer) => {
    const msg = data.toString().trim();
    console.log("[Backend]", msg);
    if (msg.includes("Application startup complete") || msg.includes("Uvicorn running")) {
      backendReady = true;
      windowManager?.getOverlayWindow()?.webContents.send("backend:ready");
    }
  });

  backendProcess.stderr?.on("data", (data: Buffer) => {
    console.error("[Backend Error]", data.toString().trim());
  });

  backendProcess.on("exit", (code) => {
    console.log("[Main] Backend exited with code:", code);
    backendReady = false;
    backendProcess = null;
  });

  // Give backend time to start, then check health
  await new Promise<void>((resolve) => {
    let attempts = 0;
    const maxAttempts = 15;

    const checkHealth = async () => {
      try {
        const response = await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/health`);
        if (response.ok) {
          backendReady = true;
          console.log("[Main] Backend health check passed");
          resolve();
          return;
        }
      } catch {
        // Backend not ready yet
      }

      attempts++;
      if (attempts >= maxAttempts) {
        console.warn("[Main] Backend health check reached retry limit; continuing to open UI...");
        resolve();
        return;
      }
      setTimeout(checkHealth, 500);
    };

    setTimeout(checkHealth, 500);
  });
}

/**
 * Stop the Python backend gracefully if we spawned it.
 */
async function stopBackend(): Promise<void> {
  try {
    await fetch(`http://${BACKEND_HOST}:${BACKEND_PORT}/shutdown`, { method: "POST" });
  } catch {
    // Backend may already be stopping
  }
  if (backendProcess) {
    backendProcess.kill("SIGTERM");
    backendProcess = null;
  }
}

/**
 * Application initialization.
 */
async function initialize(): Promise<void> {
  console.log("[Main] AI Teleprompter starting...");

  securityManager = new SecurityManager();

  // Start backend before creating windows
  await startBackend();

  // Create managers
  windowManager = new WindowManager(BACKEND_HOST, BACKEND_PORT);
  ipcManager = new IPCManager(windowManager, securityManager, BACKEND_HOST, BACKEND_PORT);
  shortcutManager = new ShortcutManager(windowManager, ipcManager);
  trayManager = new TrayManager(windowManager, shortcutManager);

  // Create the main overlay window
  await windowManager.createOverlayWindow();

  // Register global shortcuts
  shortcutManager.registerAll();

  // Create system tray
  trayManager.create();

  console.log("[Main] AI Teleprompter ready.");
}

// App event handlers
app.whenReady().then(initialize).catch((error) => {
  console.error("[Main] Initialization failed:", error);
  app.quit();
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await windowManager?.createOverlayWindow();
  }
});

app.on("before-quit", async () => {
  console.log("[Main] Shutting down...");
  shortcutManager?.unregisterAll();
  trayManager?.destroy();
  await stopBackend();
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

// Security: Prevent unauthorized new window creation from renderer
app.on("web-contents-created", (_, contents) => {
  contents.setWindowOpenHandler(() => {
    return { action: "deny" };
  });

  contents.on("will-navigate", (event, url) => {
    const parsedUrl = new URL(url);
    if (parsedUrl.origin !== "file://" && !parsedUrl.origin.startsWith("http://localhost:")) {
      event.preventDefault();
    }
  });
});

export { BACKEND_HOST, BACKEND_PORT, backendReady };
