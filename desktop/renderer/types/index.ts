// Shared types used across stores and components

export type AppState =
  | "IDLE"
  | "LISTENING"
  | "SPEECH_DETECTED"
  | "TRANSCRIBING"
  | "QUESTION_DETECTED"
  | "RETRIEVING"
  | "GENERATING"
  | "DISPLAYING"
  | "ERROR"
  | "RECOVERING";

export type AnswerMode =
  | "short"
  | "interview"
  | "technical"
  | "coding"
  | "behavioral"
  | "system_design"
  | "hr"
  | "detailed";

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export type SpeakerRole = "interviewer" | "interviewee" | "system" | "other";

export type QuestionCategory =
  | "technical"
  | "coding"
  | "system_design"
  | "project"
  | "resume"
  | "behavioral"
  | "hr"
  | "managerial"
  | "general"
  | "follow_up"
  | "unclear";

export interface Question {
  id: string;
  text: string;
  category: QuestionCategory;
  confidence: number;
  isFollowUp: boolean;
  timestamp: string;
}

export interface Answer {
  id: string;
  questionId: string;
  text: string;
  isStreaming: boolean;
  isComplete: boolean;
  sources: string[];
  mode: AnswerMode;
  latencyMs?: number;
  timestamp: string;
}

export interface TranscriptSegment {
  id: string;
  speaker: SpeakerRole;
  text: string;
  isFinal: boolean;
  timestamp: string;
}

export interface WebSocketEvent {
  id: string;
  type: string;
  timestamp: string;
  session_id: string | null;
  payload: Record<string, unknown>;
}

export interface ContextSource {
  id: string;
  name: string;
  type: string;
  relevance?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "interviewer" | "interviewee";
  text: string;
  speakerName?: string;
  isStreaming?: boolean;
  timestamp: string;
}

export interface LicenseState {
  deviceId: string;
  status: "active" | "blocked" | "expired";
  isBlocked: boolean;
  usageLimit: number;
  usageConsumed: number;
  usageRemaining: number;
  warningLevel: "warning_80" | "warning_90" | "limit_reached" | null;
  contactName: string;
  contactEmail: string;
  contactPhone: string;
  supportMessage: string;
}
