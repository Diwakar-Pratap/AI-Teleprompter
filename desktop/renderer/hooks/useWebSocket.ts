import { useEffect, useRef, useCallback } from "react";
import {
  useConnectionStore,
  useSessionStore,
  useAudioStore,
  useTranscriptStore,
  useAnswerStore,
  useChatStore,
  useSettingsStore,
  useLicenseStore,
} from "../stores";
import type { WebSocketEvent, Question, ContextSource, SpeakerRole, AppState } from "../types";

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

function getSUTInfo() {
  let deviceId = "";
  try {
    deviceId = localStorage.getItem("teleprompter_device_id") || "";
    if (deviceId.startsWith("sut_")) {
      deviceId = "";
      localStorage.removeItem("teleprompter_device_id");
      localStorage.removeItem("teleprompter_device_token");
    }
  } catch {}

  const isWin = typeof navigator !== "undefined" && navigator.userAgent.includes("Windows");
  const isMac = typeof navigator !== "undefined" && navigator.userAgent.includes("Mac");
  const osName = isWin ? "Windows" : isMac ? "macOS" : "Linux";
  const hostname = deviceId ? `SUT-${osName}-${deviceId.slice(-6).toUpperCase()}` : `SUT-${osName}-CLIENT`;

  return {
    device_id: deviceId,
    device_name: hostname,
    hostname: hostname,
    os: osName,
    os_version: typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 60) : "Unknown",
    cpu: typeof navigator !== "undefined" ? `${navigator.hardwareConcurrency || 4} Cores` : "4 Cores",
    ram: typeof navigator !== "undefined" && (navigator as any).deviceMemory ? `${(navigator as any).deviceMemory} GB` : "8 GB",
    disk_space: "50 GB",
    application_version: "0.1.0",
    agent_version: "1.0.0",
  };
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const { wsUrl, backendUrl } = useConnectionStore();

  const handleEvent = useCallback((event: WebSocketEvent) => {
    const { type, payload } = event;

    switch (type) {
      case "connection.established": {
        const isCapturing = Boolean(payload["audio_capturing"]);
        useAudioStore.getState().setCapturing(isCapturing);
        useSessionStore.getState().setListening(isCapturing);
        if (isCapturing) {
          useSessionStore.getState().setAppState("LISTENING");
        } else {
          useSessionStore.getState().setAppState("IDLE");
        }
        useTranscriptStore.getState().clearTranscript();
        useAnswerStore.getState().clearAnswer();
        useChatStore.getState().clearChat();

        const devId = (payload["device_id"] as string) || (payload["license"] as any)?.device_id;
        const devTok = (payload["device_token"] as string) || (payload["license"] as any)?.device_token;
        if (devId) {
          try {
            localStorage.setItem("teleprompter_device_id", devId);
          } catch {}
        }
        if (devTok) {
          try {
            localStorage.setItem("teleprompter_device_token", devTok);
          } catch {}
        }

        if (payload["license"]) {
          const lic = payload["license"] as Record<string, unknown>;
          const isBlk = Boolean(lic["is_blocked"]) || lic["status"] === "blocked";
          useLicenseStore.getState().setLicenseState({
            deviceId: (lic["device_id"] as string) || devId || "",
            status: (lic["status"] as "active" | "blocked" | "expired") || "active",
            isBlocked: isBlk,
            usageLimit: (lic["usage_limit"] as number) ?? 100,
            usageConsumed: (lic["usage_consumed"] as number) ?? 0,
            usageRemaining: (lic["usage_remaining"] as number) ?? 100,
            warningLevel: (lic["warning_level"] as "warning_80" | "warning_90" | "limit_reached" | null) ?? null,
            contactName: (lic["contact_name"] as string) || "Diwakar",
            contactEmail: (lic["contact_email"] as string) || "diwakar@example.com",
            contactPhone: (lic["contact_phone"] as string) || "+91-9876543210",
            supportMessage: (lic["support_message"] as string) || "For access activation or license upgrade.",
          });
          if (isBlk) {
            useSessionStore.getState().setListening(false);
            useAudioStore.getState().setCapturing(false);
          }
        }
        break;
      }

      case "session.started":
        useSessionStore.getState().setListening(true);
        useAudioStore.getState().setCapturing(true);
        useSessionStore.getState().setAppState("LISTENING");
        break;

      case "session.stopped":
        useSessionStore.getState().setListening(false);
        useAudioStore.getState().setCapturing(false);
        useSessionStore.getState().setAppState("IDLE");
        break;

      case "session.state_changed":
        if (typeof payload["current"] === "string") {
          const isL = payload["current"] === "LISTENING";
          useSessionStore.getState().setListening(isL);
          useAudioStore.getState().setCapturing(isL);
          useSessionStore.getState().setAppState(payload["current"] as AppState);
        }
        break;

      case "license.status": {
        const isBlk = Boolean(payload["is_blocked"]) || payload["status"] === "blocked";
        useLicenseStore.getState().setLicenseState({
          deviceId: (payload["device_id"] as string) || "",
          status: (payload["status"] as "active" | "blocked" | "expired") || "active",
          isBlocked: isBlk,
          usageLimit: (payload["usage_limit"] as number) ?? 100,
          usageConsumed: (payload["usage_consumed"] as number) ?? 0,
          usageRemaining: (payload["usage_remaining"] as number) ?? 100,
          warningLevel: (payload["warning_level"] as "warning_80" | "warning_90" | "limit_reached" | null) ?? null,
          contactName: (payload["contact_name"] as string) || "Diwakar",
          contactEmail: (payload["contact_email"] as string) || "diwakar@example.com",
          contactPhone: (payload["contact_phone"] as string) || "+91-9876543210",
          supportMessage: (payload["support_message"] as string) || "For access activation or license upgrade.",
        });
        if (isBlk) {
          useSessionStore.getState().setListening(false);
          useAudioStore.getState().setCapturing(false);
        }
        break;
      }

      case "license.blocked": {
        useLicenseStore.getState().setLicenseState({
          isBlocked: true,
          status: "blocked",
          usageConsumed: (payload["usage_consumed"] as number) ?? 100,
          usageLimit: (payload["usage_limit"] as number) ?? 100,
          warningLevel: "limit_reached",
          contactName: (payload["contact_name"] as string) || "Diwakar",
          supportMessage: (payload["support_message"] as string) || "For access activation or license upgrade.",
        });
        useSessionStore.getState().setListening(false);
        useAudioStore.getState().setCapturing(false);
        break;
      }

      case "audio.vad_state_changed": {
        const speaker = (payload["speaker"] as SpeakerRole) || "interviewer";
        const state = payload["state"];
        if (typeof state === "string") {
          useAudioStore.getState().setVadState(speaker, state as "SILENCE" | "SPEECH_STARTED" | "SPEAKING" | "POSSIBLE_END" | "SPEECH_ENDED");
        }
        break;
      }

      case "speech.partial":
        if (typeof payload["text"] === "string") {
          const spk = (payload["speaker"] as SpeakerRole) || "interviewer";
          useTranscriptStore.getState().setPartialText(payload["text"], spk);
        }
        break;

      case "speech.final":
        if (typeof payload["text"] === "string") {
          const spk = (payload["speaker"] as SpeakerRole) ?? "interviewer";
          useTranscriptStore.getState().addSegment({
            id: event.id,
            speaker: spk,
            text: payload["text"],
            isFinal: true,
            timestamp: event.timestamp,
          });
          useTranscriptStore.getState().setPartialText("");
          useChatStore.getState().addMessage({
            id: `speech_${event.id}`,
            role: spk === "interviewee" ? "interviewee" : "interviewer",
            text: payload["text"],
            timestamp: event.timestamp,
          });
        }
        break;

      case "question.detected":
        useSessionStore.getState().setAppState("QUESTION_DETECTED");
        useAnswerStore.getState().setQuestion({
          id: (payload["question_id"] as string) ?? event.id,
          text: (payload["question"] as string) ?? "",
          category: (payload["category"] as Question["category"]) ?? "general",
          confidence: (payload["confidence"] as number) ?? 0,
          isFollowUp: (payload["is_followup"] as boolean) ?? false,
          timestamp: event.timestamp,
        });
        break;

      case "context.search.started":
        useSessionStore.getState().setAppState("RETRIEVING");
        break;

      case "ai.request.started": {
        const qId = (payload["question_id"] as string) ?? event.id;
        useSessionStore.getState().setAppState("GENERATING");
        useChatStore.getState().addMessage({
          id: qId,
          role: "assistant",
          text: "",
          isStreaming: true,
          timestamp: event.timestamp,
        });
        break;
      }

      case "ai.token": {
        const token = payload["token"] as string;
        const qId = (payload["question_id"] as string) || "ai_stream";
        if (typeof token === "string") {
          useChatStore.getState().appendChatToken(qId, token);
          useAnswerStore.getState().appendToken(token);
          useSessionStore.getState().setAppState("GENERATING");
        }
        break;
      }

      case "ai.completed": {
        const qId = (payload["question_id"] as string) || "ai_stream";
        const answer = (payload["answer"] as string) ?? "";
        const sources = (payload["sources"] as ContextSource[]) ?? [];
        useChatStore.getState().finalizeChatMessage(qId, answer);
        useAnswerStore.getState().finalizeAnswer(answer, sources, latencyMs);
        useSessionStore.getState().setAppState("DISPLAYING");
        break;
      }

      case "ai.cancelled":
        useAnswerStore.getState().clearAnswer();
        break;

      case "audio.started":
        useAudioStore.getState().setCapturing(true);
        useSessionStore.getState().setListening(true);
        useSessionStore.getState().setAppState("LISTENING");
        break;

      case "audio.stopped":
        useAudioStore.getState().setCapturing(false);
        useSessionStore.getState().setListening(false);
        useSessionStore.getState().setAppState("IDLE");
        break;

      case "chat.token": {
        const msgId = payload["message_id"] as string;
        const token = payload["token"] as string;
        if (msgId && typeof token === "string") {
          useChatStore.getState().appendChatToken(msgId, token);
          useAnswerStore.getState().appendToken(token);
          useSessionStore.getState().setAppState("GENERATING");
        }
        break;
      }

      case "chat.completed": {
        const msgId = payload["message_id"] as string;
        const reply = payload["reply"] as string;
        if (msgId && typeof reply === "string") {
          useChatStore.getState().finalizeChatMessage(msgId, reply);
          useAnswerStore.getState().finalizeAnswer(reply, [], 0);
          useSessionStore.getState().setAppState("DISPLAYING");
        }
        break;
      }

      case "overlay.clickthrough_changed":
        if (typeof payload["enabled"] === "boolean") {
          useSettingsStore.getState().setClickThrough(payload["enabled"]);
        }
        break;

      default:
        break;
    }
  }, []);

  const sendCommand = useCallback((type: string, payload?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type,
          payload: payload ?? {},
          timestamp: new Date().toISOString(),
        })
      );
    }
  }, []);

  const registerDevice = useCallback(async () => {
    const sutInfo = getSUTInfo();
    if (!sutInfo.device_id) return;
    const urls = [
      backendUrl && backendUrl.startsWith("http") ? backendUrl : null,
      "https://salvaging-quiver-preheated.ngrok-free.dev",
      "http://127.0.0.1:8765",
    ].filter(Boolean) as string[];

    for (const targetUrl of urls) {
      try {
        const res = await fetch(`${targetUrl}/api/v1/devices/register`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "69420",
            "User-Agent": "AITeleprompter/1.0",
          },
          body: JSON.stringify(sutInfo),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.device_token) {
            try {
              localStorage.setItem("teleprompter_device_token", data.device_token);
            } catch {}
            break;
          }
        }
      } catch (e) {
        // try next url
      }
    }
  }, [backendUrl]);

  const sendHeartbeat = useCallback(async () => {
    const sutInfo = getSUTInfo();
    let token = "";
    try {
      token = localStorage.getItem("teleprompter_device_token") || "";
    } catch {}

    // 1. Send WebSocket handshake / heartbeat pulse
    if (sutInfo.device_id) {
      sendCommand("command.device_handshake", {
        ...sutInfo,
        device_token: token,
      });
    }

    if (!sutInfo.device_id) return;

    if (!token) {
      await registerDevice();
      try {
        token = localStorage.getItem("teleprompter_device_token") || "";
      } catch {}
    }

    const urls = [
      backendUrl && backendUrl.startsWith("http") ? backendUrl : null,
      "https://salvaging-quiver-preheated.ngrok-free.dev",
      "http://127.0.0.1:8765",
    ].filter(Boolean) as string[];

    // 2. Send HTTP Heartbeat
    for (const targetUrl of urls) {
      try {
        const res = await fetch(`${targetUrl}/api/v1/devices/heartbeat`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "69420",
            "User-Agent": "AITeleprompter/1.0",
          },
          body: JSON.stringify({
            device_id: sutInfo.device_id,
            device_token: token,
            hostname: sutInfo.hostname,
            app_version: "0.1.0",
            agent_version: "1.0.0",
            os: sutInfo.os,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.is_blocked) {
            useLicenseStore.getState().setLicenseState({
              isBlocked: true,
              status: "blocked",
              deviceId: sutInfo.device_id,
              usageConsumed: data.usage_consumed || 100,
              usageLimit: data.usage_limit || 100,
              contactName: data.contact_info?.contact_name || "Diwakar",
              supportMessage: data.contact_info?.support_message || "For access activation or license upgrade.",
            });
          }
          break;
        }
      } catch (e) {
        // try next
      }
    }
  }, [backendUrl, sendCommand, registerDevice]);


  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    useConnectionStore.getState().setStatus("connecting");

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      useConnectionStore.getState().setStatus("connected");
      reconnectAttempts.current = 0;
      registerDevice().then(() => sendHeartbeat());
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as WebSocketEvent;
        handleEvent(data);
      } catch (err) {
        console.error("[WebSocket] Failed to parse event:", err);
      }
    };

    ws.onerror = (error) => {
      console.error("[WebSocket] Error:", error);
      useConnectionStore.getState().setStatus("error");
    };

    ws.onclose = () => {
      useConnectionStore.getState().setStatus("disconnected");
      wsRef.current = null;

      const delay = Math.min(
        1500 * Math.pow(1.2, Math.min(reconnectAttempts.current, 8)),
        6000
      );
      reconnectAttempts.current++;
      reconnectTimer.current = setTimeout(connect, delay);
    };
  }, [wsUrl, handleEvent, registerDevice, sendHeartbeat]);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    connect();
    registerDevice().then(() => sendHeartbeat());

    // Continuous heartbeat & SUT presence pulse every 15 seconds
    const interval = setInterval(() => {
      sendHeartbeat();
    }, 15000);

    return () => {
      clearInterval(interval);
      disconnect();
    };
  }, [connect, disconnect, registerDevice, sendHeartbeat]);

  return { sendCommand, reconnect: connect };
}
