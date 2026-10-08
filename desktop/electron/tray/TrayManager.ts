import {
  Tray,
  Menu,
  nativeImage,
  app,
  type MenuItem,
  type MenuItemConstructorOptions,
} from "electron";
import { join } from "path";
import type { WindowManager } from "../windows/WindowManager";
import type { ShortcutManager } from "../shortcuts/ShortcutManager";

/**
 * TrayManager — creates and manages the system tray icon and menu.
 */
export class TrayManager {
  private tray: Tray | null = null;
  private readonly windowManager: WindowManager;
  private readonly shortcutManager: ShortcutManager;
  private isListening = false;

  constructor(windowManager: WindowManager, shortcutManager: ShortcutManager) {
    this.windowManager = windowManager;
    this.shortcutManager = shortcutManager;
  }

  /**
   * Create the tray icon and menu.
   */
  create(): void {
    // Use a blank 16x16 icon if custom icon not available
    const iconPath = join(__dirname, "../../../../assets/tray-icon.png");
    let icon: Electron.NativeImage;

    try {
      icon = nativeImage.createFromPath(iconPath);
      if (icon.isEmpty()) {
        icon = nativeImage.createEmpty();
      }
    } catch {
      icon = nativeImage.createEmpty();
    }

    this.tray = new Tray(icon);
    this.tray.setToolTip("AI Teleprompter");
    this.updateMenu();

    // Double-click to show overlay
    this.tray.on("double-click", () => {
      this.windowManager.showOverlay();
    });
  }

  /**
   * Update the tray context menu (called when state changes).
   */
  updateMenu(): void {
    if (!this.tray) return;

    const statusLabel = this.isListening ? "● Listening" : "○ Idle";

    const menuTemplate: MenuItemConstructorOptions[] = [
      {
        label: "AI Teleprompter",
        enabled: false,
      },
      {
        label: statusLabel,
        enabled: false,
      },
      { type: "separator" },
      {
        label: "Show Overlay",
        click: () => this.windowManager.showOverlay(),
      },
      {
        label: "Hide Overlay",
        click: () => this.windowManager.hideOverlay(),
      },
      { type: "separator" },
      {
        label: this.isListening ? "Stop Listening" : "Start Listening",
        click: () => {
          this.isListening = !this.isListening;
          const win = this.windowManager.getOverlayWindow();
          win?.webContents.send("shortcut:fired", {
            event: "toggle-listening",
          });
          this.updateMenu();
        },
      },
      {
        label: "Toggle Click-Through (Ctrl+Shift+M)",
        click: () => this.windowManager.toggleClickThrough(),
      },
      { type: "separator" },
      {
        label: "Context Library (Ctrl+Shift+K)",
        click: () => {
          this.windowManager.showOverlay();
          this.windowManager.getOverlayWindow()?.webContents.send("shortcut:fired", {
            event: "context-library",
          });
        },
      },
      {
        label: "Settings",
        click: () => {
          this.windowManager.showOverlay();
          this.windowManager.getOverlayWindow()?.webContents.send("shortcut:fired", {
            event: "open-settings",
          });
        },
      },
      { type: "separator" },
      {
        label: "Exit",
        click: () => app.quit(),
      },
    ];

    const menu = Menu.buildFromTemplate(menuTemplate);
    this.tray.setContextMenu(menu);
  }

  /**
   * Set listening state (updates tray menu label).
   */
  setListening(listening: boolean): void {
    this.isListening = listening;
    this.updateMenu();
  }

  /**
   * Destroy the tray icon.
   */
  destroy(): void {
    this.tray?.destroy();
    this.tray = null;
  }
}
