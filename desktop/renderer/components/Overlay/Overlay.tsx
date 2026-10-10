import React, { useState, useCallback, useEffect, useRef } from "react";
import { StatusIndicator } from "../Status/StatusIndicator";
import { CommandPalette } from "../CommandPalette/CommandPalette";
import { SettingsModal } from "../Settings/SettingsModal";
import {
  useSessionStore,
  useSettingsStore,
  useConnectionStore,
  useAudioStore,
  useAnswerStore,
  useChatStore,
  useTranscriptStore,
  useLicenseStore,
} from "../../stores";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useElectronBridge } from "../../hooks/useElectronBridge";
import { BlockedModal } from "../License/BlockedModal";
import { LicenseWarningBanner } from "../License/LicenseWarningBanner";
import { clientAudioStreamer } from "../../services/clientAudioStreamer";
import type { ChatMessage } from "../../types";

export const Overlay: React.FC = () => {
  const [isCommandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const { isClickThrough, appearance } = useSettingsStore();
  const fontSize = appearance?.fontSize || 13;
  const { isListening, setAppState } = useSessionStore();
  const { status } = useConnectionStore();
  const { vadInterviewer, vadInterviewee } = useAudioStore();
  const { clearAnswer } = useAnswerStore();
  const { messages, addMessage, clearChat, streamingMessageId } = useChatStore();
  const { partialText, partialSpeaker, clearTranscript } = useTranscriptStore();
  const { isBlocked } = useLicenseStore();

  const { sendCommand, reconnect } = useWebSocket();
  const { toggleClickThrough } = useElectronBridge(sendCommand);

  // Keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "P") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setCommandPaletteOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Auto-scroll chat to latest message or live transcription
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, partialText]);

  // Window resizing state & drag logic
  const [isResizing, setIsResizing] = useState(false);
  const resizeStartRef = useRef<{ startX: number; startY: number; startWidth: number; startHeight: number } | null>(null);

  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    resizeStartRef.current = {
      startX: e.screenX,
      startY: e.screenY,
      startWidth: window.innerWidth,
      startHeight: window.innerHeight,
    };
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!resizeStartRef.current) return;
      const dx = e.screenX - resizeStartRef.current.startX;
      const dy = e.screenY - resizeStartRef.current.startY;
      const newWidth = Math.max(320, Math.min(1400, Math.round(resizeStartRef.current.startWidth + dx)));
      const newHeight = Math.max(240, Math.min(1000, Math.round(resizeStartRef.current.startHeight + dy)));

      window.electronAPI?.send("overlay:set-size", { width: newWidth, height: newHeight });
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      resizeStartRef.current = null;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  // Size preset switcher
  const sizePresets = [
    { label: "Compact", width: 380, height: 480 },
    { label: "Standard", width: 460, height: 540 },
    { label: "Wide", width: 560, height: 540 },
    { label: "Large", width: 620, height: 680 },
  ];
  const [presetIndex, setPresetIndex] = useState(1);

  const handleCycleSize = () => {
    const nextIdx = (presetIndex + 1) % sizePresets.length;
    setPresetIndex(nextIdx);
    const preset = sizePresets[nextIdx];
    window.electronAPI?.send("overlay:set-size", { width: preset.width, height: preset.height });
  };

  // Automatically synchronize client-side audio capture & speech recognition with listening state
  useEffect(() => {
    if (isListening && !isBlocked) {
      clientAudioStreamer.start(sendCommand);
    } else {
      clientAudioStreamer.stop();
    }
  }, [isListening, isBlocked, sendCommand]);

  const handleToggleListening = useCallback(() => {
    if (isListening) {
      sendCommand("command.stop_listening");
      useSessionStore.getState().setListening(false);
      useAudioStore.getState().setCapturing(false);
      clientAudioStreamer.stop();
    } else {
      sendCommand("command.start_listening", { source: "both" });
      useSessionStore.getState().setListening(true);
      useAudioStore.getState().setCapturing(true);
      clientAudioStreamer.start(sendCommand);
    }
  }, [isListening, sendCommand]);

  const handleSendChat = useCallback(() => {
    const trimmed = chatInput.trim();
    if (!trimmed || streamingMessageId) return;

    const userMessageId = `user_${Date.now()}`;
    const assistantMessageId = `asst_${Date.now()}`;

    // Add user typed message to the unified chat stream
    addMessage({
      id: userMessageId,
      role: "user",
      text: trimmed,
      timestamp: new Date().toISOString(),
    });

    // Add streaming assistant bubble on the next line
    addMessage({
      id: assistantMessageId,
      role: "assistant",
      text: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
    });

    setAppState("GENERATING");

    sendCommand("command.chat_message", {
      message_id: assistantMessageId,
      prompt: trimmed,
    });

    setChatInput("");
  }, [chatInput, streamingMessageId, addMessage, setAppState, sendCommand]);

  const handleKeyDownChat = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendChat();
    }
  };

  const handleClear = () => {
    clearAnswer();
    clearChat();
    clearTranscript();
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const isInterviewerSpeaking =
    vadInterviewer === "SPEAKING" || vadInterviewer === "SPEECH_STARTED";
  const isIntervieweeSpeaking =
    vadInterviewee === "SPEAKING" || vadInterviewee === "SPEECH_STARTED";

  // Helper to format messages (handling DeepSeek-R1 <think> tags)
  const renderMessageContent = (msg: ChatMessage) => {
    const text = msg.text;
    if (msg.role === "assistant" && text.includes("<think>")) {
      const thinkEnd = text.indexOf("</think>");
      if (thinkEnd !== -1) {
        const thinkContent = text.substring(7, thinkEnd).trim();
        const answerContent = text.substring(thinkEnd + 8).trim();
        return (
          <div>
            {thinkContent && (
              <details
                style={{
                  marginBottom: "8px",
                  fontSize: `${Math.max(10, fontSize - 2)}px`,
                  color: "rgba(148, 163, 184, 0.85)",
                  backgroundColor: "rgba(0, 0, 0, 0.25)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  padding: "6px 8px",
                  borderRadius: "6px",
                }}
              >
                <summary style={{ cursor: "pointer", fontWeight: 600, color: "rgba(167, 139, 250, 0.95)" }}>
                  💭 Reasoning / Thought Process
                </summary>
                <div style={{ marginTop: "4px", whiteSpace: "pre-wrap", fontStyle: "italic", lineHeight: "1.4" }}>
                  {thinkContent}
                </div>
              </details>
            )}
            <div style={{ whiteSpace: "pre-wrap", lineHeight: "1.5", fontSize: `${fontSize}px` }}>{answerContent}</div>
          </div>
        );
      }
    }

    return (
      <div style={{ whiteSpace: "pre-wrap", lineHeight: "1.5", fontSize: `${fontSize}px` }}>
        {text}
        {msg.isStreaming && (
          <span
            style={{
              display: "inline-block",
              width: "6px",
              height: `${Math.max(12, fontSize)}px`,
              marginLeft: "4px",
              backgroundColor: "#60a5fa",
              verticalAlign: "middle",
              animation: "pulse 1s infinite",
            }}
          />
        )}
      </div>
    );
  };

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "rgba(13, 17, 23, 0.96)",
        border: "1px solid rgba(255, 255, 255, 0.12)",
        borderRadius: "12px",
        overflow: "hidden",
        boxShadow: "0 20px 40px rgba(0, 0, 0, 0.7)",
      }}
    >
      {isClickThrough && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: "2px",
            zIndex: 50,
            backgroundColor: "rgba(251, 191, 36, 0.8)",
          }}
        />
      )}

      {/* Header — drag region with live VAD indicators and controls */}
      <div
        className="drag-region"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          backgroundColor: "rgba(255, 255, 255, 0.03)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <StatusIndicator />

          {/* Speaker activity indicators */}
          <div
            className="no-drag"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "2px 8px",
              borderRadius: "4px",
              backgroundColor: "rgba(0, 0, 0, 0.35)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
            }}
          >
            {/* Interviewer (System Audio Loopback) */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "10px",
                color: isInterviewerSpeaking ? "#34d399" : "rgba(136, 146, 164, 0.6)",
                fontWeight: isInterviewerSpeaking ? 600 : 400,
                transition: "all 0.15s ease",
              }}
              title="Interviewer (System Audio Loopback capture)"
            >
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: isInterviewerSpeaking ? "#34d399" : "rgba(136, 146, 164, 0.3)",
                  boxShadow: isInterviewerSpeaking ? "0 0 8px #34d399" : "none",
                }}
              />
              Interviewer
            </div>

            <span style={{ color: "rgba(255, 255, 255, 0.15)" }}>|</span>

            {/* Interviewee (Microphone) */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "10px",
                color: isIntervieweeSpeaking ? "#60a5fa" : "rgba(136, 146, 164, 0.6)",
                fontWeight: isIntervieweeSpeaking ? 600 : 400,
                transition: "all 0.15s ease",
              }}
              title="You (Microphone capture)"
            >
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: isIntervieweeSpeaking ? "#60a5fa" : "rgba(136, 146, 164, 0.3)",
                  boxShadow: isIntervieweeSpeaking ? "0 0 8px #60a5fa" : "none",
                }}
              />
              You (Mic)
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="no-drag" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {/* Listening button */}
          <button
            onClick={handleToggleListening}
            style={{
              padding: "2px 8px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              gap: "5px",
              background: isListening ? "rgba(239, 68, 68, 0.18)" : "rgba(255, 255, 255, 0.05)",
              border: isListening ? "1px solid rgba(239, 68, 68, 0.45)" : "1px solid rgba(255, 255, 255, 0.1)",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            title={isListening ? "Listening is active (Click to Stop Listening)" : "Listening is paused (Click to Start Listening)"}
          >
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                backgroundColor: isListening ? "#ef4444" : "rgba(136, 146, 164, 0.5)",
                boxShadow: isListening ? "0 0 8px #ef4444" : "none",
                display: "inline-block",
              }}
            />
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: isListening ? "#fca5a5" : "rgba(136, 146, 164, 0.8)",
              }}
            >
              {isListening ? "Listening" : "Paused"}
            </span>
          </button>

          {/* Clear button */}
          <button
            onClick={handleClear}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "rgba(136, 146, 164, 0.6)",
            }}
            title="Clear chat and speech history"
          >
            <svg style={{ width: "13px", height: "13px" }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>

          {/* Settings button */}
          <button
            onClick={() => setSettingsOpen(true)}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
            }}
            title="Settings & Knowledge Base (⚙️)"
          >
            <span style={{ fontSize: "13px" }}>⚙️</span>
          </button>

          {/* Resize Presets cycle button */}
          <button
            onClick={handleCycleSize}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "rgba(136, 146, 164, 0.75)",
            }}
            title={`Resize window: ${sizePresets[presetIndex].label} (${sizePresets[presetIndex].width}x${sizePresets[presetIndex].height}) — click to switch`}
          >
            <svg style={{ width: "13px", height: "13px" }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>

          {/* Command palette */}
          <button
            onClick={() => setCommandPaletteOpen(true)}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
            }}
            title="Command palette (Ctrl+Shift+P)"
          >
            <svg
              style={{ width: "14px", height: "14px", color: "rgba(136, 146, 164, 0.8)" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
            </svg>
          </button>

          {/* Click-through toggle */}
          <button
            onClick={toggleClickThrough}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
            }}
            title="Toggle click-through (Ctrl+Shift+M)"
          >
            <svg
              style={{
                width: "14px",
                height: "14px",
                color: isClickThrough ? "rgba(251, 191, 36, 0.9)" : "rgba(136, 146, 164, 0.6)",
              }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5" />
            </svg>
          </button>

          {/* Minimize button */}
          <button
            onClick={() => window.electronAPI?.send("app:minimize")}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "rgba(136, 146, 164, 0.7)",
              transition: "background 0.15s ease, color 0.15s ease",
            }}
            title="Minimize window"
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(255, 255, 255, 0.08)";
              (e.currentTarget as HTMLElement).style.color = "#e6edf3";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              (e.currentTarget as HTMLElement).style.color = "rgba(136, 146, 164, 0.7)";
            }}
          >
            <svg style={{ width: "12px", height: "12px" }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 12H5" />
            </svg>
          </button>

          {/* Close button */}
          <button
            onClick={() => {
              if (window.electronAPI) {
                window.electronAPI.send("app:quit");
              } else {
                window.close();
              }
            }}
            style={{
              width: "24px",
              height: "24px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "rgba(136, 146, 164, 0.7)",
              transition: "background 0.15s ease, color 0.15s ease",
            }}
            title="Close AI Teleprompter"
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(239, 68, 68, 0.85)";
              (e.currentTarget as HTMLElement).style.color = "#ffffff";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "transparent";
              (e.currentTarget as HTMLElement).style.color = "rgba(136, 146, 164, 0.7)";
            }}
          >
            <svg style={{ width: "13px", height: "13px" }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* License Warning Banner */}
      <LicenseWarningBanner />

      {/* Main Content: Unified Conversational Chat Stream */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          padding: "12px",
          gap: "10px",
        }}
      >
        {messages.map((m) => {
          const isInterviewer = m.role === "interviewer";
          const isUser = m.role === "user" || m.role === "interviewee";
          const isAssistant = m.role === "assistant";

          return (
            <div
              key={m.id}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                padding: "8px 12px",
                borderRadius: "8px",
                backgroundColor: isInterviewer
                  ? "rgba(16, 185, 129, 0.08)"
                  : isUser
                  ? "rgba(59, 130, 246, 0.08)"
                  : "rgba(255, 255, 255, 0.03)",
                border: isInterviewer
                  ? "1px solid rgba(16, 185, 129, 0.2)"
                  : isUser
                  ? "1px solid rgba(59, 130, 246, 0.2)"
                  : "1px solid rgba(255, 255, 255, 0.08)",
                fontSize: `${fontSize}px`,
                color: "rgba(230, 237, 243, 0.95)",
              }}
            >
              {/* Message Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span
                    style={{
                      fontSize: `${Math.max(10, fontSize - 2)}px`,
                      fontWeight: 600,
                      color: isInterviewer
                        ? "#34d399"
                        : isUser
                        ? "#60a5fa"
                        : "#a78bfa",
                    }}
                  >
                    {isInterviewer
                      ? "🎙️ Interviewer"
                      : m.role === "interviewee"
                      ? "🎤 You (Spoken)"
                      : isUser
                      ? "💬 You (Prompt)"
                      : "🤖 AI Co-pilot"}
                  </span>
                  <span style={{ fontSize: `${Math.max(9, fontSize - 3)}px`, color: "rgba(136, 146, 164, 0.5)" }}>
                    {new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>

                {isAssistant && m.text && (
                  <button
                    onClick={() => handleCopy(m.id, m.text)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: copiedId === m.id ? "#34d399" : "rgba(136, 146, 164, 0.6)",
                      fontSize: `${Math.max(10, fontSize - 2)}px`,
                      cursor: "pointer",
                      padding: "2px 4px",
                    }}
                    title="Copy response"
                  >
                    {copiedId === m.id ? "✓ Copied" : "Copy"}
                  </button>
                )}
              </div>

              {/* Message Content */}
              <div>{renderMessageContent(m)}</div>
            </div>
          );
        })}

        {/* Live Word-by-Word In-Progress Transcription Bubble */}
        {partialText && (
          <div
            style={{
              padding: "8px 12px",
              borderRadius: "8px",
              backgroundColor: "rgba(251, 191, 36, 0.08)",
              border: "1px dashed rgba(251, 191, 36, 0.4)",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <span style={{ fontSize: `${Math.max(10, fontSize - 2)}px`, fontWeight: 600, color: "#fbbf24" }}>
                🎙️ {partialSpeaker === "interviewer" ? "Interviewer" : "You"} (speaking...)
              </span>
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: "#fbbf24",
                  animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
                }}
              />
            </div>
            <div style={{ fontSize: `${fontSize}px`, color: "#fef08a", lineHeight: "1.4" }}>
              {partialText}
              <span
                style={{
                  display: "inline-block",
                  width: "6px",
                  height: `${Math.max(12, fontSize)}px`,
                  marginLeft: "4px",
                  backgroundColor: "#fbbf24",
                  verticalAlign: "middle",
                }}
              />
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Bottom Bar: Input for Chat / Custom Prompts */}
      <div
        className="no-drag"
        style={{
          padding: "8px 12px",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          backgroundColor: "rgba(255, 255, 255, 0.02)",
          display: "flex",
          gap: "8px",
          alignItems: "center",
        }}
      >
        <textarea
          ref={chatInputRef}
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={handleKeyDownChat}
          placeholder={
            isBlocked
              ? "Application locked — Free usage limit reached. Contact Diwakar."
              : "Ask AI, clarify question, or brainstorm... (Press Enter)"
          }
          rows={1}
          style={{
            flex: 1,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            borderRadius: "6px",
            padding: "8px 10px",
            color: "rgba(230, 237, 243, 0.95)",
            fontSize: `${fontSize}px`,
            lineHeight: "1.4",
            resize: "none",
            outline: "none",
            maxHeight: "70px",
          }}
          disabled={Boolean(streamingMessageId) || isBlocked}
        />
        <button
          onClick={handleSendChat}
          disabled={!chatInput.trim() || Boolean(streamingMessageId) || isBlocked}
          style={{
            padding: "8px 14px",
            borderRadius: "6px",
            border: "none",
            backgroundColor:
              chatInput.trim() && !streamingMessageId
                ? "rgba(59, 130, 246, 0.9)"
                : "rgba(255, 255, 255, 0.08)",
            color:
              chatInput.trim() && !streamingMessageId
                ? "#ffffff"
                : "rgba(136, 146, 164, 0.4)",
            cursor: chatInput.trim() && !streamingMessageId ? "pointer" : "default",
            fontSize: "11px",
            fontWeight: 600,
            whiteSpace: "nowrap",
          }}
        >
          {streamingMessageId ? "Thinking..." : "Ask AI"}
        </button>
      </div>

      {/* Footer Branding & Author Credit */}
      <div
        className="no-drag"
        style={{
          padding: "3px 12px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderTop: "1px solid rgba(255, 255, 255, 0.04)",
          backgroundColor: "rgba(0, 0, 0, 0.3)",
          fontSize: "10px",
          color: "rgba(148, 163, 184, 0.65)",
          userSelect: "none",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <span style={{ color: "#818cf8" }}>⚡</span> AI Teleprompter
        </span>
        <span style={{ fontWeight: 500, color: "rgba(167, 139, 250, 0.9)" }}>
          Developed by Diwakar Pratap
        </span>
      </div>

      {/* Status banner if disconnected */}
      {status !== "connected" && (
        <div
          onClick={() => reconnect()}
          className="no-drag"
          style={{
            padding: "6px 12px",
            textAlign: "center",
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            cursor: "pointer",
          }}
          title="Click to retry connecting to backend immediately"
        >
          <span style={{ fontSize: "11px", color: "rgba(248, 113, 113, 0.95)", fontWeight: 500 }}>
            {status === "connecting"
              ? "Connecting to backend (http://127.0.0.1:8765)..."
              : "Backend disconnected — click here to reconnect 🔄"}
          </span>
        </div>
      )}

      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        sendCommand={sendCommand}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setSettingsOpen(false)}
      />

      {/* Interactive Corner Resize Drag Handle */}
      <div
        onMouseDown={handleResizeMouseDown}
        className="no-drag"
        title="Drag corner to freely resize window"
        style={{
          position: "absolute",
          right: 3,
          bottom: 3,
          width: 18,
          height: 18,
          cursor: "se-resize",
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "flex-end",
          padding: "2px",
          zIndex: 80,
          opacity: 0.75,
          userSelect: "none",
        }}
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M11 2L2 11M11 6L6 11M11 10L10 11" stroke="rgba(255, 255, 255, 0.6)" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>

      {/* Right Edge Resize Handle */}
      <div
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsResizing(true);
          resizeStartRef.current = {
            startX: e.screenX,
            startY: e.screenY,
            startWidth: window.innerWidth,
            startHeight: window.innerHeight,
          };
        }}
        className="no-drag"
        title="Drag edge to resize width"
        style={{
          position: "absolute",
          top: 40,
          right: 0,
          bottom: 20,
          width: 5,
          cursor: "ew-resize",
          zIndex: 75,
        }}
      />

      {/* Bottom Edge Resize Handle */}
      <div
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsResizing(true);
          resizeStartRef.current = {
            startX: e.screenX,
            startY: e.screenY,
            startWidth: window.innerWidth,
            startHeight: window.innerHeight,
          };
        }}
        className="no-drag"
        title="Drag edge to resize height"
        style={{
          position: "absolute",
          bottom: 0,
          left: 10,
          right: 20,
          height: 5,
          cursor: "ns-resize",
          zIndex: 75,
        }}
      />

      {/* Professional Blocking Modal for License Exhaustion */}
      <BlockedModal />
    </div>
  );
};

export default Overlay;
