import {
  BrowserWindow,
  screen,
  type Display,
} from "electron";
import { join } from "path";
import { is } from "@electron-toolkit/utils";

export interface WindowBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OverlayConfig {
  opacity: number;
  width: number;
  height: number;
  x?: number;
  y?: number;
  monitorIndex?: number;
}

const DEFAULT_CONFIG: OverlayConfig = {
  opacity: 1.0,
  width: 460,
  height: 540,
  monitorIndex: 0,
};

/**
 * WindowManager — manages the lifecycle of all application windows.
 */
export class WindowManager {
  private overlayWindow: BrowserWindow | null = null;
  private config: OverlayConfig = { ...DEFAULT_CONFIG };
  private isClickThrough = false;
  private readonly backendHost: string;
  private readonly backendPort: number;

  constructor(backendHost: string, backendPort: number) {
    this.backendHost = backendHost;
    this.backendPort = backendPort;
  }

  async createOverlayWindow(): Promise<BrowserWindow> {
    const display = this.getTargetDisplay();
    const { x, y } = this.calculatePosition(display);

    const preloadPath = join(__dirname, "../preload/index.js");

    this.overlayWindow = new BrowserWindow({
      x,
      y,
      width: this.config.width,
      height: this.config.height,
      frame: false,
      transparent: true,
      backgroundColor: "#00000000",
      alwaysOnTop: true,
      skipTaskbar: true,
      type: "toolbar",
      focusable: true,
      resizable: true,
      movable: true,
      minimizable: false,
      maximizable: false,
      fullscreenable: false,
      webPreferences: {
        preload: preloadPath,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
        webSecurity: true,
      },
      show: true,
      hasShadow: false,
      minWidth: 320,
      minHeight: 220,
    });

    try {
      this.overlayWindow.setAlwaysOnTop(true, "screen-saver");
      this.overlayWindow.setSkipTaskbar(true);
    } catch (err) {
      console.warn("[WindowManager] Failed to set always-on-top level:", err);
    }

    // Exclude teleprompter overlay from screen capture, screen recordings, and screen sharing (Zoom, Meet, Teams, Discord)
    try {
      this.overlayWindow.setContentProtection(true);
      console.log("[WindowManager] Content protection enabled (excluded from screen capture)");
    } catch (err) {
      console.warn("[WindowManager] Failed to set content protection:", err);
    }

    if (is.dev && process.env["ELECTRON_RENDERER_URL"]) {
      console.log("[WindowManager] Loading URL:", process.env["ELECTRON_RENDERER_URL"]);
      await this.overlayWindow.loadURL(process.env["ELECTRON_RENDERER_URL"]);
    } else {
      const filePath = join(__dirname, "../renderer/index.html");
      console.log("[WindowManager] Loading file:", filePath);
      await this.overlayWindow.loadFile(filePath);
    }

    this.overlayWindow.show();
    this.overlayWindow.focus();

    this.overlayWindow.on("closed", () => {
      this.overlayWindow = null;
    });

    this.overlayWindow.webContents.on("did-finish-load", () => {
      console.log("[WindowManager] Renderer did-finish-load");
      this.overlayWindow?.webContents.send("app:state-changed", {
        backendUrl: `http://${this.backendHost}:${this.backendPort}`,
        wsUrl: `ws://${this.backendHost}:${this.backendPort}/ws/events`,
        isClickThrough: this.isClickThrough,
        opacity: this.config.opacity,
      });
    });

    return this.overlayWindow;
  }

  getOverlayWindow(): BrowserWindow | null {
    return this.overlayWindow;
  }

  showOverlay(): void {
    this.overlayWindow?.show();
    this.overlayWindow?.focus();
  }

  hideOverlay(): void {
    this.overlayWindow?.hide();
  }

  toggleOverlay(): void {
    if (this.overlayWindow?.isVisible()) {
      this.hideOverlay();
    } else {
      this.showOverlay();
    }
  }

  toggleClickThrough(): boolean {
    this.isClickThrough = !this.isClickThrough;
    this.applyClickThrough();
    this.overlayWindow?.webContents.send("overlay:clickthrough-changed", {
      enabled: this.isClickThrough,
    });
    return this.isClickThrough;
  }

  setClickThrough(enabled: boolean): void {
    this.isClickThrough = enabled;
    this.applyClickThrough();
    this.overlayWindow?.webContents.send("overlay:clickthrough-changed", {
      enabled: this.isClickThrough,
    });
  }

  private applyClickThrough(): void {
    if (this.overlayWindow) {
      this.overlayWindow.setIgnoreMouseEvents(this.isClickThrough, {
        forward: true,
      });
    }
  }

  setOpacity(opacity: number): void {
    const clamped = Math.max(0.1, Math.min(1.0, opacity));
    this.config.opacity = clamped;
    this.overlayWindow?.setOpacity(clamped);
    this.overlayWindow?.webContents.send("overlay:opacity-changed", {
      opacity: clamped,
    });
  }

  getOpacity(): number {
    return this.config.opacity;
  }

  getClickThrough(): boolean {
    return this.isClickThrough;
  }

  setContentProtection(enabled: boolean): void {
    try {
      this.overlayWindow?.setContentProtection(enabled);
      console.log(`[WindowManager] Content protection set to: ${enabled}`);
    } catch (err) {
      console.warn("[WindowManager] Failed to set content protection:", err);
    }
  }

  moveToMonitor(monitorIndex: number): void {
    const displays = screen.getAllDisplays();
    if (monitorIndex >= 0 && monitorIndex < displays.length) {
      const display = displays[monitorIndex];
      this.config.monitorIndex = monitorIndex;
      const { x, y } = this.calculatePosition(display);
      this.overlayWindow?.setPosition(x, y);
    }
  }

  setPosition(x: number, y: number): void {
    this.overlayWindow?.setPosition(x, y);
  }

  setSize(width: number, height: number): void {
    const w = Math.max(300, width);
    const h = Math.max(200, height);
    this.config.width = w;
    this.config.height = h;
    this.overlayWindow?.setSize(w, h);
  }

  getBounds(): WindowBounds | null {
    if (!this.overlayWindow) return null;
    return this.overlayWindow.getBounds();
  }

  getAllDisplays(): Display[] {
    return screen.getAllDisplays();
  }

  private getTargetDisplay(): Display {
    const displays = screen.getAllDisplays();
    const index = this.config.monitorIndex ?? 0;
    return displays[Math.min(index, displays.length - 1)] ?? displays[0];
  }

  private calculatePosition(display: Display): { x: number; y: number } {
    const { bounds } = display;
    const margin = 40;
    const x = bounds.x + bounds.width - this.config.width - margin;
    const y = bounds.y + margin;
    return { x, y };
  }
}
