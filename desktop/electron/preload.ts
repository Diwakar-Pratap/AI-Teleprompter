import { contextBridge, ipcRenderer } from "electron";

/**
 * Preload script — defines the safe API surface exposed to the renderer.
 *
 * Security principles:
 * - contextIsolation: true (enforced by Electron)
 * - nodeIntegration: false (enforced by Electron)
 * - Only explicitly allowlisted IPC channels are accessible
 * - No raw Node.js access from renderer
 */

// Allowlisted IPC channels (renderer -> main)
const ALLOWED_SEND_CHANNELS = [
  "overlay:toggle-clickthrough",
  "overlay:set-opacity",
  "overlay:set-content-protection",
  "overlay:set-position",
  "overlay:set-size",
  "overlay:show",
  "overlay:hide",
  "overlay:move-to-monitor",
  "shortcut:trigger",
  "command:execute",
  "app:quit",
  "app:minimize",
  "settings:get",
  "settings:set",
  "backend:get-token",
] as const;

// Allowlisted IPC channels (main -> renderer)
const ALLOWED_RECEIVE_CHANNELS = [
  "backend:ready",
  "backend:status",
  "overlay:clickthrough-changed",
  "overlay:opacity-changed",
  "shortcut:fired",
  "app:state-changed",
  "window:moved",
  "window:resized",
] as const;

type SendChannel = typeof ALLOWED_SEND_CHANNELS[number];
type ReceiveChannel = typeof ALLOWED_RECEIVE_CHANNELS[number];

/**
 * The electronAPI object is the ONLY way the renderer can interact with
 * the Electron main process. Keep this surface minimal.
 */
const electronAPI = {
  // Send a message to the main process
  send: (channel: SendChannel, data?: unknown) => {
    if (ALLOWED_SEND_CHANNELS.includes(channel)) {
      ipcRenderer.send(channel, data);
    } else {
      console.warn("[Preload] Blocked send to unauthorized channel:", channel);
    }
  },

  // Send and await a response
  invoke: async (channel: SendChannel, data?: unknown): Promise<unknown> => {
    if (ALLOWED_SEND_CHANNELS.includes(channel)) {
      return ipcRenderer.invoke(channel, data);
    }
    console.warn("[Preload] Blocked invoke to unauthorized channel:", channel);
    return null;
  },

  // Subscribe to messages from main process
  on: (channel: ReceiveChannel, callback: (...args: unknown[]) => void) => {
    if (ALLOWED_RECEIVE_CHANNELS.includes(channel)) {
      const handler = (_event: Electron.IpcRendererEvent, ...args: unknown[]) => callback(...args);
      ipcRenderer.on(channel, handler);
      // Return cleanup function
      return () => ipcRenderer.removeListener(channel, handler);
    }
    console.warn("[Preload] Blocked subscribe to unauthorized channel:", channel);
    return () => {};
  },

  // Subscribe once
  once: (channel: ReceiveChannel, callback: (...args: unknown[]) => void) => {
    if (ALLOWED_RECEIVE_CHANNELS.includes(channel)) {
      ipcRenderer.once(channel, (_event, ...args) => callback(...args));
    }
  },

  // Platform info (safe to expose)
  platform: process.platform,
  version: process.env.npm_package_version ?? "0.1.0",
};

// Expose to renderer under window.electronAPI
contextBridge.exposeInMainWorld("electronAPI", electronAPI);

// Type declaration for renderer TypeScript
export type ElectronAPI = typeof electronAPI;
