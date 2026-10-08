import {
  ipcMain,
  type IpcMainInvokeEvent,
  type IpcMainEvent,
} from "electron";
import type { WindowManager } from "../windows/WindowManager";
import type { SecurityManager } from "../security/SecurityManager";

/**
 * IPCManager — handles all IPC communication between renderer and main process.
 *
 * Security principles:
 * - All inputs are validated before acting
 * - Only allowlisted operations are supported
 * - No API keys or credentials flow through IPC to renderer
 */
export class IPCManager {
  private readonly windowManager: WindowManager;
  private readonly securityManager: SecurityManager;
  private readonly backendHost: string;
  private readonly backendPort: number;

  constructor(
    windowManager: WindowManager,
    securityManager: SecurityManager,
    backendHost: string,
    backendPort: number
  ) {
    this.windowManager = windowManager;
    this.securityManager = securityManager;
    this.backendHost = backendHost;
    this.backendPort = backendPort;

    this.registerHandlers();
  }

  /**
   * Register all IPC handlers.
   */
  private registerHandlers(): void {
    // Overlay controls
    ipcMain.on("overlay:toggle-clickthrough", () => {
      this.windowManager.toggleClickThrough();
    });

    ipcMain.on("overlay:set-opacity", (_event: IpcMainEvent, opacity: unknown) => {
      if (typeof opacity === "number") {
        this.windowManager.setOpacity(opacity);
      }
    });

    ipcMain.on("overlay:set-content-protection", (_event: IpcMainEvent, enabled: unknown) => {
      if (typeof enabled === "boolean") {
        this.windowManager.setContentProtection(enabled);
      }
    });

    ipcMain.on("overlay:set-position", (_event: IpcMainEvent, data: unknown) => {
      if (
        data &&
        typeof data === "object" &&
        "x" in data &&
        "y" in data &&
        typeof (data as { x: unknown }).x === "number" &&
        typeof (data as { y: unknown }).y === "number"
      ) {
        const { x, y } = data as { x: number; y: number };
        this.windowManager.setPosition(x, y);
      }
    });

    ipcMain.on("overlay:set-size", (_event: IpcMainEvent, data: unknown) => {
      if (
        data &&
        typeof data === "object" &&
        "width" in data &&
        "height" in data &&
        typeof (data as { width: unknown }).width === "number" &&
        typeof (data as { height: unknown }).height === "number"
      ) {
        const { width, height } = data as { width: number; height: number };
        this.windowManager.setSize(width, height);
      }
    });

    ipcMain.on("overlay:show", () => this.windowManager.showOverlay());
    ipcMain.on("overlay:hide", () => this.windowManager.hideOverlay());

    ipcMain.on("overlay:move-to-monitor", (_event: IpcMainEvent, index: unknown) => {
      if (typeof index === "number") {
        this.windowManager.moveToMonitor(index);
      }
    });

    // App controls
    ipcMain.on("app:quit", async () => {
      try {
        await fetch(`http://${this.backendHost}:${this.backendPort}/shutdown`, { method: "POST" });
      } catch {
        // ignore
      }
      const { app } = require("electron");
      app.quit();
    });

    ipcMain.on("app:minimize", () => {
      this.windowManager.getOverlayWindow()?.minimize();
    });

    // Backend URL / token (safe to expose — localhost only)
    ipcMain.handle("backend:get-token", async (): Promise<string> => {
      return this.securityManager.getBackendToken();
    });

    // Settings pass-through (backend handles actual persistence)
    ipcMain.handle("settings:get", async (): Promise<{ backendUrl: string; wsUrl: string }> => {
      return {
        backendUrl: `http://${this.backendHost}:${this.backendPort}`,
        wsUrl: `ws://${this.backendHost}:${this.backendPort}/ws/events`,
      };
    });

    // Shortcut trigger from renderer (command palette etc.)
    ipcMain.on("shortcut:trigger", (_event: IpcMainEvent, shortcutId: unknown) => {
      if (typeof shortcutId === "string") {
        console.log("[IPCManager] Shortcut triggered from renderer:", shortcutId);
        // Notify renderer back
        this.windowManager.getOverlayWindow()?.webContents.send("shortcut:fired", {
          event: shortcutId,
        });
      }
    });

    // Generic command execution
    ipcMain.on("command:execute", (_event: IpcMainEvent, command: unknown) => {
      if (typeof command === "string") {
        this.handleCommand(command);
      }
    });
  }

  private handleCommand(command: string): void {
    switch (command) {
      case "toggle-overlay":
        this.windowManager.toggleOverlay();
        break;
      case "toggle-clickthrough":
        this.windowManager.toggleClickThrough();
        break;
      default:
        console.warn("[IPCManager] Unknown command:", command);
    }
  }
}
