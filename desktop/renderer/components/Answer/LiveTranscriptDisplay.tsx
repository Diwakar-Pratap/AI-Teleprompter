import React from "react";
import { useTranscriptStore, useAudioStore } from "../../stores";

export const LiveTranscriptDisplay: React.FC = () => {
  const { segments, partialText } = useTranscriptStore();
  const { vadInterviewer, vadInterviewee } = useAudioStore();

  const isInterviewerSpeaking =
    vadInterviewer === "SPEAKING" || vadInterviewer === "SPEECH_STARTED";
  const isIntervieweeSpeaking =
    vadInterviewee === "SPEAKING" || vadInterviewee === "SPEECH_STARTED";

  const latestSegment = segments.length > 0 ? segments[segments.length - 1] : null;

  const partialSpeaker = isIntervieweeSpeaking
    ? "interviewee"
    : isInterviewerSpeaking
    ? "interviewer"
    : latestSegment?.speaker ?? "interviewer";

  return (
    <div
      style={{
        padding: "6px 12px",
        backgroundColor: "rgba(0, 0, 0, 0.22)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        minHeight: "38px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: "3px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "10px",
          fontWeight: 600,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          color: "rgba(136, 146, 164, 0.65)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span>LIVE CAPTIONS</span>
          {(partialText || isInterviewerSpeaking || isIntervieweeSpeaking) && (
            <span
              style={{
                display: "inline-block",
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                backgroundColor: isIntervieweeSpeaking ? "#60a5fa" : "#34d399",
                boxShadow: isIntervieweeSpeaking
                  ? "0 0 6px #60a5fa"
                  : "0 0 6px #34d399",
              }}
            />
          )}
        </div>

        <span
          style={{
            fontSize: "10px",
            color:
              partialSpeaker === "interviewer"
                ? "rgba(52, 211, 153, 0.9)"
                : "rgba(96, 165, 250, 0.9)",
            fontWeight: 500,
          }}
        >
          {partialSpeaker === "interviewer" ? "🎙️ Interviewer" : "🎤 You"}
        </span>
      </div>

      <div style={{ fontSize: "12px", lineHeight: "1.4" }}>
        {partialText ? (
          <span style={{ color: "rgba(243, 244, 246, 0.95)" }}>
            <strong
              style={{
                color:
                  partialSpeaker === "interviewer"
                    ? "#34d399"
                    : "#60a5fa",
                marginRight: "4px",
                fontWeight: 600,
              }}
            >
              {partialSpeaker === "interviewer" ? "Interviewer:" : "You:"}
            </strong>
            <span style={{ fontStyle: "italic", opacity: 0.95 }}>{partialText}</span>
          </span>
        ) : latestSegment ? (
          <span style={{ color: "rgba(229, 231, 235, 0.9)" }}>
            <strong
              style={{
                color:
                  latestSegment.speaker === "interviewer"
                    ? "#34d399"
                    : "#60a5fa",
                marginRight: "4px",
                fontWeight: 600,
              }}
            >
              {latestSegment.speaker === "interviewer" ? "Interviewer:" : "You:"}
            </strong>
            <span>{latestSegment.text}</span>
          </span>
        ) : (
          <span style={{ color: "rgba(136, 146, 164, 0.4)", fontStyle: "italic", fontSize: "11px" }}>
            Listening... (interviews & microphone speech will appear here live)
          </span>
        )}
      </div>
    </div>
  );
};
