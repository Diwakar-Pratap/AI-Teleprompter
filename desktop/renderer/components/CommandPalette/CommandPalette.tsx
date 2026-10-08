import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAnswerStore, useSessionStore } from "../../stores";

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  action: () => void;
  group: string;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  sendCommand: (type: string, payload?: Record<string, unknown>) => void;
}

/**
 * CommandPalette — keyboard-driven command interface.
 * Opened via Ctrl+Shift+P.
 */
export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  sendCommand,
}) => {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const { clearAnswer } = useAnswerStore();
  const { setMode, isListening } = useSessionStore();

  const commands: Command[] = [
    {
      id: "start-listening",
      label: isListening ? "Stop Listening" : "Start Listening",
      shortcut: "Ctrl+Shift+L",
      group: "Session",
      action: () => sendCommand("command.toggle_listening"),
    },
    {
      id: "regenerate",
      label: "Regenerate Answer",
      shortcut: "Ctrl+Shift+R",
      group: "Answer",
      action: () => sendCommand("command.regenerate"),
    },
    {
      id: "clear",
      label: "Clear Answer",
      shortcut: "Ctrl+Shift+C",
      group: "Answer",
      action: () => {
        clearAnswer();
        sendCommand("command.cancel");
      },
    },
    {
      id: "mode-short",
      label: "Short Answer Mode",
      shortcut: "Ctrl+Shift+S",
      group: "Mode",
      action: () => {
        setMode("short");
        sendCommand("command.set_mode", { mode: "short" });
      },
    },
    {
      id: "mode-technical",
      label: "Technical Answer Mode",
      shortcut: "Ctrl+Shift+T",
      group: "Mode",
      action: () => {
        setMode("technical");
        sendCommand("command.set_mode", { mode: "technical" });
      },
    },
    {
      id: "mode-behavioral",
      label: "Behavioral Answer Mode",
      group: "Mode",
      action: () => {
        setMode("behavioral");
        sendCommand("command.set_mode", { mode: "behavioral" });
      },
    },
    {
      id: "mode-coding",
      label: "Coding Answer Mode",
      group: "Mode",
      action: () => {
        setMode("coding");
        sendCommand("command.set_mode", { mode: "coding" });
      },
    },
    {
      id: "screenshot",
      label: "Take Screenshot",
      shortcut: "Ctrl+Shift+X",
      group: "Tools",
      action: () => sendCommand("command.take_screenshot"),
    },
  ];

  const filtered = commands.filter(
    (c) =>
      c.label.toLowerCase().includes(query.toLowerCase()) ||
      c.group.toLowerCase().includes(query.toLowerCase())
  );

  const execute = useCallback(
    (command: Command) => {
      command.action();
      onClose();
      setQuery("");
    },
    [onClose]
  );

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        break;
      case "Enter":
        e.preventDefault();
        if (filtered[selectedIndex]) {
          execute(filtered[selectedIndex]);
        }
        break;
      case "Escape":
        onClose();
        break;
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="no-drag absolute inset-0 z-50 flex items-start justify-center pt-12"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="w-full max-w-xs rounded-xl overflow-hidden shadow-2xl border"
        style={{
          background: "rgba(12, 14, 20, 0.97)",
          borderColor: "rgba(255,255,255,0.10)",
        }}
      >
        {/* Search input */}
        <div
          className="flex items-center gap-2 px-3 py-2.5 border-b"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <svg
            className="w-3.5 h-3.5 flex-shrink-0"
            style={{ color: "rgba(136, 146, 164, 0.6)" }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            ref={inputRef}
            type="text"
            placeholder="Search commands..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-slate-600"
            style={{ color: "rgba(232, 234, 240, 0.9)" }}
          />
        </div>

        {/* Command list */}
        <div className="max-h-64 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div
              className="px-3 py-4 text-center text-xs"
              style={{ color: "rgba(136, 146, 164, 0.5)" }}
            >
              No commands found
            </div>
          ) : (
            filtered.map((command, index) => (
              <button
                key={command.id}
                className="no-drag w-full text-left px-3 py-2 flex items-center justify-between group transition-colors"
                style={{
                  background:
                    index === selectedIndex
                      ? "rgba(79, 156, 249, 0.12)"
                      : "transparent",
                }}
                onClick={() => execute(command)}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs"
                    style={{ color: "rgba(136, 146, 164, 0.45)" }}
                  >
                    {command.group}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "rgba(232, 234, 240, 0.80)" }}
                  >
                    {command.label}
                  </span>
                </div>
                {command.shortcut && (
                  <span
                    className="text-xs font-mono px-1 rounded"
                    style={{
                      color: "rgba(136, 146, 164, 0.5)",
                      background: "rgba(255,255,255,0.04)",
                    }}
                  >
                    {command.shortcut}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
