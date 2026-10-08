import { useEffect, useCallback } from "react";
import {
  useSettingsStore,
  useSessionStore,
  useConnectionStore,
  useAnswerStore,
} from "../stores";

declare global {
  interface Window {
    electronAPI?: {
      send: (channel: string, data?: unknown) => void;
      invoke: (channel: string, data?: unknown) => Promise<unknown>;
      on: (channel: string, callback: (...args: unknown[]) => void) => () => void;
      once: (channel: string, callback: (...args: unknown[]) => void) => void;
      platform: string;
      version: string;
    };
  }
}

export function useElectronBridge(sendCommand: (type: string, payload?: Record<string, unknown>) => void) {
  const { setClickThrough, setOpacity } = useSettingsStore();
  const { setMode } = useSessionStore();
  const { setUrls } = useConnectionStore();
  const { clearAnswer } = useAnswerStore();

  const isElectron = typeof window !== "undefined" && !!window.electronAPI;

  const handleShortcut = useCallback(
    (event: string, payload?: Record<string, unknown>) => {
      switch (event) {
        case "toggle-listening":
          sendCommand("command.toggle_listening");
          break;
        case "toggle-clickthrough":
          if (payload && typeof payload["enabled"] === "boolean") {
            setClickThrough(payload["enabled"]);
          }
          break;
        case "regenerate":
          sendCommand("command.regenerate");
          break;
        case "short-answer":
          setMode("short");
          sendCommand("command.set_mode", { mode: "short" });
          break;
        case "technical-answer":
          setMode("technical");
          sendCommand("command.set_mode", { mode: "technical" });
          break;
        case "clear-answer":
          clearAnswer();
          sendCommand("command.cancel");
          break;
        case "screenshot":
          sendCommand("command.take_screenshot");
          break;
        default:
          break;
      }
    },
    [sendCommand, setClickThrough, setMode, clearAnswer]
  );

  useEffect(() => {
    if (!isElectron) return;

    const api = window.electronAPI!;

    api.invoke("settings:get").then((config) => {
      const cfg = config as { backendUrl: string; wsUrl: string } | null;
      if (cfg?.backendUrl && cfg?.wsUrl) {
        setUrls(cfg.backendUrl, cfg.wsUrl);
      }
    });

    const unsubShortcut = api.on("shortcut:fired", (...args) => {
      const data = args[0] as { event: string; payload?: Record<string, unknown> };
      handleShortcut(data.event, data.payload);
    });

    const unsubClickThrough = api.on("overlay:clickthrough-changed", (...args) => {
      const data = args[0] as { enabled: boolean };
      setClickThrough(data.enabled);
    });

    const unsubOpacity = api.on("overlay:opacity-changed", (...args) => {
      const data = args[0] as { opacity: number };
      setOpacity(data.opacity);
    });

    const unsubState = api.on("app:state-changed", (...args) => {
      const data = args[0] as {
        backendUrl?: string;
        wsUrl?: string;
        isClickThrough?: boolean;
        opacity?: number;
      };
      if (data.backendUrl && data.wsUrl) {
        setUrls(data.backendUrl, data.wsUrl);
      }
      if (data.isClickThrough !== undefined) {
        setClickThrough(data.isClickThrough);
      }
      if (data.opacity !== undefined) {
        setOpacity(data.opacity);
      }
    });

    return () => {
      unsubShortcut();
      unsubClickThrough();
      unsubOpacity();
      unsubState();
    };
  }, [isElectron, handleShortcut, setClickThrough, setOpacity, setUrls]);

  const toggleClickThrough = useCallback(() => {
    window.electronAPI?.send("overlay:toggle-clickthrough");
  }, []);

  const setWindowOpacity = useCallback((opacity: number) => {
    window.electronAPI?.send("overlay:set-opacity", opacity);
  }, []);

  const setContentProtection = useCallback((enabled: boolean) => {
    window.electronAPI?.send("overlay:set-content-protection", enabled);
  }, []);

  return {
    isElectron,
    toggleClickThrough,
    setWindowOpacity,
    setContentProtection,
  };
}
