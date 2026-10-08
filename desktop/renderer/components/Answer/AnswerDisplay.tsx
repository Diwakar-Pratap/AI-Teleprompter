import React, { useRef, useEffect } from "react";
import { useAnswerStore, useSessionStore } from "../../stores";

interface AnswerDisplayProps {
  maxHeight?: number;
}

/**
 * AnswerDisplay — renders the streaming/completed AI answer.
 * Uses a streaming cursor while generating.
 */
export const AnswerDisplay: React.FC<AnswerDisplayProps> = ({
  maxHeight = 360,
}) => {
  const { currentAnswer, streamingText, sources } = useAnswerStore();
  const { appState } = useSessionStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const isGenerating = appState === "GENERATING";
  const displayText = currentAnswer?.text ?? streamingText;

  // Auto-scroll to bottom while streaming
  useEffect(() => {
    if (scrollRef.current && isGenerating) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayText, isGenerating]);

  if (!displayText && !isGenerating) {
    return (
      <div className="px-3 py-2">
        <div
          className="text-xs font-semibold tracking-widest uppercase mb-1"
          style={{ color: "rgba(136, 146, 164, 0.6)" }}
        >
          Answer
        </div>
        <div className="text-sm" style={{ color: "rgba(232, 234, 240, 0.35)" }}>
          Waiting for a question...
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-2 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div
          className="text-xs font-semibold tracking-widest uppercase"
          style={{ color: "rgba(136, 146, 164, 0.6)" }}
        >
          Answer
        </div>
        {currentAnswer?.latencyMs && (
          <span
            className="text-xs"
            style={{ color: "rgba(136, 146, 164, 0.45)" }}
          >
            {(currentAnswer.latencyMs / 1000).toFixed(1)}s
          </span>
        )}
      </div>

      <div
        ref={scrollRef}
        className="overflow-y-auto"
        style={{ maxHeight: `${maxHeight}px` }}
      >
        <p
          className={`text-sm leading-relaxed whitespace-pre-wrap ${
            isGenerating ? "streaming-cursor" : ""
          }`}
          style={{ color: "rgba(232, 234, 240, 0.92)" }}
        >
          {displayText}
        </p>
      </div>

      {/* Sources */}
      {sources.length > 0 && !isGenerating && (
        <div
          className="mt-1 pt-1 border-t"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <span
            className="text-xs"
            style={{ color: "rgba(136, 146, 164, 0.55)" }}
          >
            Sources:{" "}
            {sources.map((s) => s.name).join(" · ")}
          </span>
        </div>
      )}
    </div>
  );
};
