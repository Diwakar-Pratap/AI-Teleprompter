import { globalShortcut } from "electron";
import type { WindowManager } from "../windows/WindowManager";
import type { IPCManager } from "../ipc/IPCManager";

export interface ShortcutDefinition {
  accelerator: string;
  description: string;
  action: () => void;
}

/**
 * ShortcutManager — registers and manages global keyboard shortcuts.
 *
 * Shortcuts are defined here and stored in settings.
 * Do not hardcode shortcut handling inside UI components.
 */
export class ShortcutManager {
  private readonly windowManager: WindowManager;
  private readonly ipcManager: IPCManager;
  private shortcuts: Map<string, ShortcutDefinition> = new Map();

  constructor(windowManager: WindowManager, ipcManager: IPCManager) {
    this.windowManager = windowManager;
    this.ipcManager = ipcManager;
  }

  /**
   * Register all default shortcuts.
   */
  registerAll(): void {
    this.defineShortcuts();

    for (const [id, shortcut] of this.shortcuts) {
      const registered = globalShortcut.register(shortcut.accelerator, shortcut.action);
      if (!registered) {
        console.warn(`[ShortcutManager] Failed to register shortcut: ${id} (${shortcut.accelerator})`);
      } else {
        console.log(`[ShortcutManager] Registered: ${shortcut.accelerator} -> ${id}`);
      }
    }
  }

  /**
   * Unregister all shortcuts (call on app quit).
   */
  unregisterAll(): void {
    globalShortcut.unregisterAll();
    this.shortcuts.clear();
  }

  /**
   * Update a shortcut accelerator.
   */
  updateShortcut(id: string, newAccelerator: string): boolean {
    const existing = this.shortcuts.get(id);
    if (!existing) return false;

    // Unregister old
    globalShortcut.unregister(existing.accelerator);

    // Register new
    const registered = globalShortcut.register(newAccelerator, existing.action);
    if (registered) {
      this.shortcuts.set(id, { ...existing, accelerator: newAccelerator });
    }
    return registered;
  }

  /**
   * Get all registered shortcut definitions.
   */
  getAllShortcuts(): Array<{ id: string } & ShortcutDefinition> {
    return Array.from(this.shortcuts.entries()).map(([id, def]) => ({ id, ...def }));
  }

  private defineShortcuts(): void {
    const win = this.windowManager;
    const overlay = this.windowManager.getOverlayWindow();

    const notify = (event: string, payload?: unknown) => {
      win.getOverlayWindow()?.webContents.send("shortcut:fired", { event, payload });
    };

    this.shortcuts.set("toggle-overlay", {
      accelerator: "Ctrl+Shift+Space",
      description: "Show/hide overlay",
      action: () => {
        win.toggleOverlay();
        notify("toggle-overlay");
      },
    });

    this.shortcuts.set("toggle-listening", {
      accelerator: "Ctrl+Shift+L",
      description: "Start/stop listening",
      action: () => notify("toggle-listening"),
    });

    this.shortcuts.set("command-palette", {
      accelerator: "Ctrl+Shift+P",
      description: "Open command palette",
      action: () => {
        win.showOverlay();
        notify("command-palette");
      },
    });

    this.shortcuts.set("context-library", {
      accelerator: "Ctrl+Shift+K",
      description: "Open context library",
      action: () => {
        win.showOverlay();
        notify("context-library");
      },
    });

    this.shortcuts.set("screenshot", {
      accelerator: "Ctrl+Shift+X",
      description: "Take screenshot",
      action: () => notify("screenshot"),
    });

    this.shortcuts.set("regenerate", {
      accelerator: "Ctrl+Shift+R",
      description: "Regenerate answer",
      action: () => notify("regenerate"),
    });

    this.shortcuts.set("short-answer", {
      accelerator: "Ctrl+Shift+S",
      description: "Short answer mode",
      action: () => notify("short-answer"),
    });

    this.shortcuts.set("technical-answer", {
      accelerator: "Ctrl+Shift+T",
      description: "Technical answer mode",
      action: () => notify("technical-answer"),
    });

    this.shortcuts.set("clear-answer", {
      accelerator: "Ctrl+Shift+C",
      description: "Clear current answer",
      action: () => notify("clear-answer"),
    });

    this.shortcuts.set("toggle-clickthrough", {
      accelerator: "Ctrl+Shift+M",
      description: "Toggle click-through mode",
      action: () => {
        const enabled = win.toggleClickThrough();
        notify("toggle-clickthrough", { enabled });
      },
    });
  }
}
