import React from "react";
import { useAnswerStore } from "../../stores";

const CATEGORY_LABELS: Record<string, string> = {
  technical: "Technical",
  coding: "Coding",
  system_design: "System Design",
  project: "Project",
  resume: "Resume",
  behavioral: "Behavioral",
  hr: "HR",
  managerial: "Managerial",
  general: "General",
  follow_up: "Follow-up",
  unclear: "Unclear",
};

const CATEGORY_COLORS: Record<string, string> = {
  technical: "text-blue-300 border-blue-800",
  coding: "text-violet-300 border-violet-800",
  system_design: "text-cyan-300 border-cyan-800",
  project: "text-teal-300 border-teal-800",
  behavioral: "text-amber-300 border-amber-800",
  hr: "text-rose-300 border-rose-800",
  general: "text-slate-300 border-slate-700",
  follow_up: "text-orange-300 border-orange-800",
  resume: "text-green-300 border-green-800",
  managerial: "text-purple-300 border-purple-800",
  unclear: "text-slate-400 border-slate-700",
};

/**
 * QuestionDisplay — renders the detected question with category badge.
 */
export const QuestionDisplay: React.FC = () => {
  const { currentQuestion } = useAnswerStore();

  if (!currentQuestion) {
    return (
      <div className="px-3 py-2">
        <div
          className="text-xs font-semibold tracking-widest uppercase mb-1"
          style={{ color: "rgba(136, 146, 164, 0.6)" }}
        >
          Question
        </div>
        <div className="text-sm" style={{ color: "rgba(232, 234, 240, 0.35)" }}>
          Waiting...
        </div>
      </div>
    );
  }

  const categoryColor =
    CATEGORY_COLORS[currentQuestion.category] ?? CATEGORY_COLORS["general"];

  return (
    <div className="px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <div
          className="text-xs font-semibold tracking-widest uppercase"
          style={{ color: "rgba(136, 146, 164, 0.6)" }}
        >
          Question
        </div>
        <span
          className={`text-xs px-1.5 py-0.5 rounded border ${categoryColor} bg-transparent`}
        >
          {CATEGORY_LABELS[currentQuestion.category] ?? "General"}
        </span>
      </div>
      <p
        className="text-sm leading-relaxed"
        style={{ color: "rgba(232, 234, 240, 0.90)" }}
      >
        {currentQuestion.text}
      </p>
      {currentQuestion.isFollowUp && (
        <div
          className="mt-1 text-xs"
          style={{ color: "rgba(251, 191, 36, 0.7)" }}
        >
          ↩ Follow-up
        </div>
      )}
    </div>
  );
};
