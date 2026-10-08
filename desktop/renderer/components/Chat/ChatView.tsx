import React, { useState, useRef, useEffect } from "react";
import { useChatStore } from "../../stores";
import type { ChatMessage } from "../../types";

interface ChatViewProps {
  sendCommand: (type: string, payload?: Record<string, unknown>) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({ sendCommand }) => {
  const { messages, addMessage, clearChat, streamingMessageId } = useChatStore();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || streamingMessageId) return;

    const userMessageId = `user_${Date.now()}`;
    const assistantMessageId = `asst_${Date.now()}`;

    // Add user message
    const userMsg: ChatMessage = {
      id: userMessageId,
      role: "user",
      text: trimmed,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMsg);

    // Prepare streaming assistant response placeholder
    const asstMsg: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      text: "",
      isStreaming: true,
      timestamp: new Date().toISOString(),
    };
    addMessage(asstMsg);

    // Send command to backend via WebSocket
    sendCommand("command.chat_message", {
      message_id: assistantMessageId,
      prompt: trimmed,
    });

    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: "rgba(13, 17, 23, 0.4)",
      }}
    >
      {/* Chat header bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "6px 12px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        }}
      >
        <span style={{ fontSize: "11px", color: "rgba(136, 146, 164, 0.8)", fontWeight: 500 }}>
          Interactive AI Chat
        </span>
        <button
          onClick={clearChat}
          style={{
            background: "none",
            border: "none",
            fontSize: "11px",
            color: "rgba(136, 146, 164, 0.6)",
            cursor: "pointer",
            padding: "2px 6px",
            borderRadius: "4px",
          }}
          title="Clear conversation"
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = "rgba(248, 113, 113, 0.9)")}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = "rgba(136, 146, 164, 0.6)")}
        >
          Clear
        </button>
      </div>

      {/* Message list */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: isUser ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "85%",
                  padding: "8px 12px",
                  borderRadius: isUser ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                  backgroundColor: isUser
                    ? "rgba(59, 130, 246, 0.25)"
                    : "rgba(255, 255, 255, 0.05)",
                  border: isUser
                    ? "1px solid rgba(59, 130, 246, 0.4)"
                    : "1px solid rgba(255, 255, 255, 0.08)",
                  color: "rgba(230, 237, 243, 0.95)",
                  fontSize: "13px",
                  lineHeight: "1.45",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  boxShadow: isUser
                    ? "0 2px 6px rgba(59, 130, 246, 0.15)"
                    : "0 2px 6px rgba(0, 0, 0, 0.2)",
                }}
              >
                {msg.text || (msg.isStreaming && (
                  <span style={{ color: "rgba(136, 146, 164, 0.6)", fontStyle: "italic" }}>
                    Thinking...
                  </span>
                ))}
                {msg.isStreaming && msg.text && (
                  <span
                    style={{
                      display: "inline-block",
                      width: "6px",
                      height: "14px",
                      backgroundColor: "rgba(79, 156, 249, 0.8)",
                      marginLeft: "4px",
                      verticalAlign: "middle",
                      animation: "pulse 1s infinite",
                    }}
                  />
                )}
              </div>
              <span
                style={{
                  fontSize: "9px",
                  color: "rgba(136, 146, 164, 0.5)",
                  marginTop: "3px",
                  padding: "0 4px",
                }}
              >
                {isUser ? "You" : "AI"} •{" "}
                {new Date(msg.timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div
        style={{
          padding: "8px 10px",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          backgroundColor: "rgba(255, 255, 255, 0.02)",
          display: "flex",
          gap: "8px",
          alignItems: "flex-end",
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question or practice answering... (Enter to send)"
          rows={1}
          style={{
            flex: 1,
            backgroundColor: "rgba(0, 0, 0, 0.35)",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "6px",
            padding: "8px 10px",
            color: "rgba(230, 237, 243, 0.95)",
            fontSize: "12px",
            lineHeight: "1.4",
            resize: "none",
            outline: "none",
            maxHeight: "80px",
          }}
          disabled={Boolean(streamingMessageId)}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || Boolean(streamingMessageId)}
          style={{
            padding: "8px 14px",
            borderRadius: "6px",
            border: "none",
            backgroundColor:
              input.trim() && !streamingMessageId
                ? "rgba(59, 130, 246, 0.85)"
                : "rgba(255, 255, 255, 0.08)",
            color:
              input.trim() && !streamingMessageId
                ? "#ffffff"
                : "rgba(136, 146, 164, 0.4)",
            cursor: input.trim() && !streamingMessageId ? "pointer" : "default",
            fontSize: "12px",
            fontWeight: 500,
            transition: "all 0.15s ease",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
};
