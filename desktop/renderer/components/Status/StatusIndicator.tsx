import React, { useMemo } from "react";
import { useConnectionStore, useSessionStore, useAudioStore } from "../../stores";
import type { ConnectionStatus, AppState } from "../../types";

interface StatusIndicatorProps {
  className?: string;
}

function getStatusColor(status: ConnectionStatus, appState: AppState): string {
  if (status !== "connected") return "text-red-400";
  switch (appState) {
    case "LISTENING":
    case "SPEECH_DETECTED":
      return "text-emerald-400";
    case "TRANSCRIBING":
    case "QUESTION_DETECTED":
      return "text-yellow-400";
    case "RETRIEVING":
    case "GENERATING":
      return "text-blue-400";
    case "DISPLAYING":
      return "text-purple-400";
    case "ERROR":
    case "RECOVERING":
      return "text-red-400";
    default:
      return "text-slate-400";
  }
}

function getStatusLabel(
  status: ConnectionStatus,
  appState: AppState,
  isListening: boolean
): string {
  if (status === "connecting") return "Connecting...";
  if (status === "disconnected") return "Disconnected";
  if (status === "error") return "Connection Error";

  switch (appState) {
    case "IDLE":
      return isListening ? "Ready" : "Idle";
    case "LISTENING":
      return "Listening";
    case "SPEECH_DETECTED":
      return "Speech Detected";
    case "TRANSCRIBING":
      return "Transcribing...";
    case "QUESTION_DETECTED":
      return "Question Detected";
    case "RETRIEVING":
      return "Retrieving Context...";
    case "GENERATING":
      return "Generating...";
    case "DISPLAYING":
      return "Answer Ready";
    case "ERROR":
      return "Error";
    case "RECOVERING":
      return "Recovering...";
    default:
      return "Unknown";
  }
}

/**
 * StatusIndicator — shows connection status and application state.
 * Minimal, always visible at the top of the overlay.
 */
export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ className = "" }) => {
  const { status } = useConnectionStore();
  const { appState, isListening } = useSessionStore();
  const { vadInterviewer, vadInterviewee } = useAudioStore();

  const colorClass = useMemo(
    () => getStatusColor(status, appState),
    [status, appState]
  );

  const label = useMemo(
    () => getStatusLabel(status, appState, isListening),
    [status, appState, isListening]
  );

  const isActive =
    appState === "LISTENING" ||
    appState === "SPEECH_DETECTED" ||
    vadInterviewer === "SPEAKING" ||
    vadInterviewee === "SPEAKING";

  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      {/* Status dot */}
      <span className={`relative inline-flex w-2 h-2 ${colorClass}`}>
        <span
          className={`inline-block w-2 h-2 rounded-full bg-current ${
            isActive ? "animate-pulse" : ""
          }`}
        />
      </span>

      {/* Status label */}
      <span
        className="text-xs font-medium tracking-wide"
        style={{ color: "rgba(232, 234, 240, 0.75)" }}
      >
        {label}
      </span>
    </div>
  );
};
