import { create } from "zustand";
import type {
  AppState,
  AnswerMode,
  ConnectionStatus,
  Question,
  Answer,
  TranscriptSegment,
  ContextSource,
  ChatMessage,
  SpeakerRole,
} from "../types";

// ─── Connection Store ─────────────────────────────────────────────────────────
interface ConnectionStore {
  status: ConnectionStatus;
  backendUrl: string;
  wsUrl: string;
  backendVersion: string;
  setStatus: (status: ConnectionStatus) => void;
  setUrls: (backendUrl: string, wsUrl: string) => void;
  setVersion: (version: string) => void;
}

export const useConnectionStore = create<ConnectionStore>((set) => ({
  status: "disconnected",
  backendUrl: "https://salvaging-quiver-preheated.ngrok-free.dev",
  wsUrl: "wss://salvaging-quiver-preheated.ngrok-free.dev/ws/events",
  backendVersion: "",
  setStatus: (status) => set({ status }),
  setUrls: (backendUrl, wsUrl) => set({ backendUrl, wsUrl }),
  setVersion: (version) => set({ backendVersion: version }),
}));

// ─── Session Store ─────────────────────────────────────────────────────────────
interface SessionStore {
  sessionId: string | null;
  appState: AppState;
  isListening: boolean;
  mode: AnswerMode;
  activeTab: "prompter" | "chat";
  startSession: (sessionId: string) => void;
  stopSession: () => void;
  setAppState: (state: AppState) => void;
  setListening: (listening: boolean) => void;
  setMode: (mode: AnswerMode) => void;
  setActiveTab: (tab: "prompter" | "chat") => void;
}

export const useSessionStore = create<SessionStore>((set) => ({
  sessionId: null,
  appState: "IDLE",
  isListening: false,
  mode: "interview",
  activeTab: "prompter",
  startSession: (sessionId) =>
    set({ sessionId, appState: "LISTENING", isListening: true }),
  stopSession: () =>
    set({ sessionId: null, appState: "IDLE", isListening: false }),
  setAppState: (appState) => set({ appState }),
  setListening: (isListening) =>
    set({ isListening, appState: isListening ? "LISTENING" : "IDLE" }),
  setMode: (mode) => set({ mode }),
  setActiveTab: (activeTab) => set({ activeTab }),
}));

// ─── Audio Store ──────────────────────────────────────────────────────────────
interface AudioStore {
  isCapturing: boolean;
  source: "system" | "microphone" | "both";
  vadInterviewer: "SILENCE" | "SPEECH_STARTED" | "SPEAKING" | "POSSIBLE_END" | "SPEECH_ENDED";
  vadInterviewee: "SILENCE" | "SPEECH_STARTED" | "SPEAKING" | "POSSIBLE_END" | "SPEECH_ENDED";
  setCapturing: (capturing: boolean) => void;
  setSource: (source: "system" | "microphone" | "both") => void;
  setVadState: (speaker: SpeakerRole, state: AudioStore["vadInterviewer"]) => void;
}

export const useAudioStore = create<AudioStore>((set) => ({
  isCapturing: false,
  source: "both",
  vadInterviewer: "SILENCE",
  vadInterviewee: "SILENCE",
  setCapturing: (isCapturing) => set({ isCapturing }),
  setSource: (source) => set({ source }),
  setVadState: (speaker, state) => {
    if (speaker === "interviewer") {
      set({ vadInterviewer: state });
    } else if (speaker === "interviewee") {
      set({ vadInterviewee: state });
    }
  },
}));

// ─── Transcript Store ─────────────────────────────────────────────────────────
interface TranscriptStore {
  segments: TranscriptSegment[];
  partialText: string;
  partialSpeaker: SpeakerRole;
  addSegment: (segment: TranscriptSegment) => void;
  setPartialText: (text: string, speaker?: SpeakerRole) => void;
  clearTranscript: () => void;
}

export const useTranscriptStore = create<TranscriptStore>((set) => ({
  segments: [],
  partialText: "",
  partialSpeaker: "interviewer",
  addSegment: (segment) =>
    set((state) => ({
      segments: [...state.segments.slice(-50), segment],
      partialText: segment.isFinal ? "" : state.partialText,
    })),
  setPartialText: (partialText, speaker) =>
    set((state) => ({
      partialText,
      partialSpeaker: speaker || state.partialSpeaker,
    })),
  clearTranscript: () => set({ segments: [], partialText: "" }),
}));

// ─── Answer Store ─────────────────────────────────────────────────────────────
interface AnswerStore {
  currentQuestion: Question | null;
  currentAnswer: Answer | null;
  streamingText: string;
  sources: ContextSource[];
  setQuestion: (question: Question | null) => void;
  setAnswer: (answer: Answer | null) => void;
  appendToken: (token: string) => void;
  finalizeAnswer: (fullText: string, sources: ContextSource[], latencyMs: number) => void;
  clearAnswer: () => void;
  setSources: (sources: ContextSource[]) => void;
}

export const useAnswerStore = create<AnswerStore>((set) => ({
  currentQuestion: null,
  currentAnswer: null,
  streamingText: "",
  sources: [],
  setQuestion: (currentQuestion) =>
    set({ currentQuestion, streamingText: "", currentAnswer: null, sources: [] }),
  setAnswer: (currentAnswer) => set({ currentAnswer }),
  appendToken: (token) =>
    set((state) => ({
      streamingText: state.streamingText + token,
      currentAnswer: state.currentAnswer
        ? {
            ...state.currentAnswer,
            text: state.currentAnswer.text + token,
            isStreaming: true,
          }
        : null,
    })),
  finalizeAnswer: (fullText, sources, latencyMs) =>
    set((state) => ({
      streamingText: fullText,
      sources,
      currentAnswer: state.currentAnswer
        ? {
            ...state.currentAnswer,
            text: fullText,
            isStreaming: false,
            isComplete: true,
            sources: sources.map((s) => s.name),
            latencyMs,
          }
        : null,
    })),
  clearAnswer: () =>
    set({ currentQuestion: null, currentAnswer: null, streamingText: "", sources: [] }),
  setSources: (sources) => set({ sources }),
}));

// ─── Chat Store (Interactive Chatbot) ─────────────────────────────────────────
interface ChatStore {
  messages: ChatMessage[];
  streamingMessageId: string | null;
  addMessage: (message: ChatMessage) => void;
  appendChatToken: (messageId: string, token: string) => void;
  finalizeChatMessage: (messageId: string, fullText: string) => void;
  clearChat: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [
    {
      id: "welcome",
      role: "assistant",
      text: "👋 AI Teleprompter Co-pilot is online! Start speaking or type a question below.",
      timestamp: new Date().toISOString(),
    },
  ],
  streamingMessageId: null,
  addMessage: (message) =>
    set((state) => {
      // Ignore if identical message id already exists
      if (state.messages.some((m) => m.id === message.id)) {
        return state;
      }
      // Ignore if exact same text and role was added as the immediate previous message
      const lastMsg = state.messages[state.messages.length - 1];
      if (lastMsg && lastMsg.role === message.role && lastMsg.text.trim() === message.text.trim() && message.text.trim().length > 0) {
        return state;
      }
      return {
        messages: [...state.messages, message],
        streamingMessageId: message.isStreaming ? message.id : state.streamingMessageId,
      };
    }),
  appendChatToken: (messageId, token) =>
    set((state) => {
      const exists = state.messages.some((m) => m.id === messageId);
      if (!exists) {
        return {
          messages: [
            ...state.messages,
            {
              id: messageId,
              role: "assistant",
              text: token,
              isStreaming: true,
              timestamp: new Date().toISOString(),
            },
          ],
          streamingMessageId: messageId,
        };
      }
      return {
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, text: m.text + token, isStreaming: true } : m
        ),
        streamingMessageId: messageId,
      };
    }),
  finalizeChatMessage: (messageId, fullText) =>
    set((state) => {
      const exists = state.messages.some((m) => m.id === messageId);
      if (!exists) {
        return {
          streamingMessageId: null,
          messages: [
            ...state.messages,
            {
              id: messageId,
              role: "assistant",
              text: fullText,
              isStreaming: false,
              timestamp: new Date().toISOString(),
            },
          ],
        };
      }
      return {
        streamingMessageId: null,
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, text: fullText, isStreaming: false } : m
        ),
      };
    }),
  clearChat: () =>
    set({
      messages: [
        {
          id: `welcome_${Date.now()}`,
          role: "assistant",
          text: "👋 AI Teleprompter Co-pilot is online! Start speaking or type a question below.",
          timestamp: new Date().toISOString(),
        },
      ],
      streamingMessageId: null,
    }),
}));

// ─── Settings Store ────────────────────────────────────────────────────────────
interface AppearanceSettings {
  opacity: number;
  fontSize: number;
  width: number;
  maxAnswerHeight: number;
  showQuestion: boolean;
  showSources: boolean;
  theme: "dark";
}

interface SettingsStore {
  appearance: AppearanceSettings;
  isClickThrough: boolean;
  showDevPanel: boolean;
  setOpacity: (opacity: number) => void;
  setClickThrough: (enabled: boolean) => void;
  setFontSize: (size: number) => void;
  toggleDevPanel: () => void;
  updateAppearance: (settings: Partial<AppearanceSettings>) => void;
}

const getInitialFontSize = (): number => {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const saved = localStorage.getItem("ai_teleprompter_font_size");
      if (saved) return parseInt(saved, 10) || 13;
    }
  } catch {
    // ignore
  }
  return 13;
};

export const useSettingsStore = create<SettingsStore>((set) => ({
  appearance: {
    opacity: 0.95,
    fontSize: getInitialFontSize(),
    width: 460,
    maxAnswerHeight: 400,
    showQuestion: true,
    showSources: true,
    theme: "dark",
  },
  isClickThrough: false,
  showDevPanel: false,
  setOpacity: (opacity) =>
    set((state) => ({
      appearance: { ...state.appearance, opacity },
    })),
  setClickThrough: (isClickThrough) => set({ isClickThrough }),
  setFontSize: (fontSize) => {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        localStorage.setItem("ai_teleprompter_font_size", String(fontSize));
      }
    } catch {
      // ignore
    }
    set((state) => ({
      appearance: { ...state.appearance, fontSize },
    }));
  },
  toggleDevPanel: () =>
    set((state) => ({ showDevPanel: !state.showDevPanel })),
  updateAppearance: (settings) =>
    set((state) => ({
      appearance: { ...state.appearance, ...settings },
    })),
}));

// ─── License Store ─────────────────────────────────────────────────────────────
interface LicenseStore {
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
  setLicenseState: (data: Partial<LicenseStore>) => void;
  setBlocked: (blocked: boolean) => void;
}

export const useLicenseStore = create<LicenseStore>((set) => ({
  deviceId: "",
  status: "active",
  isBlocked: false,
  usageLimit: 100,
  usageConsumed: 0,
  usageRemaining: 100,
  warningLevel: null,
  contactName: "Diwakar",
  contactEmail: "diwakar@example.com",
  contactPhone: "+91-9876543210",
  supportMessage: "For access activation or license upgrade.",
  setLicenseState: (data) => set((state) => ({ ...state, ...data })),
  setBlocked: (isBlocked) => set({ isBlocked, status: isBlocked ? "blocked" : "active" }),
}));

