import React, { useState, useEffect, useRef } from "react";
import { useConnectionStore, useSettingsStore } from "../../stores";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface KnowledgeDoc {
  id: string;
  title: string;
  doc_type: string;
  word_count: number;
  created_at: string;
  source_filename?: string;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<"api" | "knowledge" | "window">("api");
  const { backendUrl } = useConnectionStore();
  const { appearance, setFontSize } = useSettingsStore();
  const currentFontSize = appearance?.fontSize || 13;
  const effectiveBackendUrl = backendUrl && backendUrl.startsWith("http") ? backendUrl : "http://127.0.0.1:8765";

  // Window Size State
  const [winWidth, setWinWidth] = useState<number>(window.innerWidth || 460);
  const [winHeight, setWinHeight] = useState<number>(window.innerHeight || 540);

  const applyWindowSize = (w: number, h: number) => {
    setWinWidth(w);
    setWinHeight(h);
    window.electronAPI?.send("overlay:set-size", { width: w, height: h });
  };

  // API Settings State
  const [provider, setProvider] = useState<string>("claude");
  const [apiKey, setApiKey] = useState<string>("");
  const [model, setModel] = useState<string>("claude-3-5-sonnet-20241022");
  const [personaType, setPersonaType] = useState<string>("natural_human");
  const [customPersonaText, setCustomPersonaText] = useState<string>("");
  const [testStatus, setTestStatus] = useState<{
    testing: boolean;
    success?: boolean;
    message?: string;
    latency?: number;
  }>({ testing: false });
  const [saveStatus, setSaveStatus] = useState<string>("");

  // Knowledge Base State
  const [documents, setDocuments] = useState<KnowledgeDoc[]>([]);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [uploading, setUploading] = useState(false);
  const [addingNote, setAddingNote] = useState(false);
  const [knowledgeMessage, setKnowledgeMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [configuredProviders, setConfiguredProviders] = useState<Record<string, { configured: boolean; preview: string }>>({});

  // Fetch initial API status & knowledge documents
  useEffect(() => {
    if (isOpen) {
      fetchApiConfig();
      fetchKnowledgeDocs();
    }
  }, [isOpen]);

  const fetchApiConfig = async () => {
    try {
      const res = await fetch(`${effectiveBackendUrl}/api/v1/settings/api-keys`);
      if (res.ok) {
        const data = await res.json();
        if (data.active_provider) {
          setProvider(data.active_provider);
        }
        if (data.active_model) {
          setModel(data.active_model);
        }
        if (data.persona) {
          if (["natural_human", "concise", "interview_star", "technical"].includes(data.persona)) {
            setPersonaType(data.persona);
          } else {
            setPersonaType("custom");
            setCustomPersonaText(data.persona);
          }
        }
        if (data.providers) {
          setConfiguredProviders(data.providers);
        }
      }
    } catch (err) {
      console.warn("Failed to load API keys info:", err);
    }
  };

  const fetchKnowledgeDocs = async () => {
    try {
      const res = await fetch(`${effectiveBackendUrl}/api/v1/knowledge`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.warn("Failed to load knowledge documents:", err);
    }
  };

  const handleTestConnection = async () => {
    const isConfigured = configuredProviders[provider]?.configured;
    if (!apiKey.trim() && !isConfigured) {
      setTestStatus({
        testing: false,
        success: false,
        message: "Please enter an API key to test.",
      });
      return;
    }

    setTestStatus({ testing: true, message: "Testing connection..." });
    try {
      const res = await fetch(`${effectiveBackendUrl}/api/v1/settings/test-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          api_key: apiKey.trim(),
          model: model.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        setTestStatus({
          testing: false,
          success: false,
          message: `Backend returned HTTP ${res.status}: ${errText.slice(0, 150)}`,
        });
        return;
      }

      const data = await res.json();
      let displayMsg = data.message || (data.success ? "Connection successful!" : "Connection failed");
      if (data.details && data.details !== "Model responded to ping." && !displayMsg.includes(data.details)) {
        displayMsg += ` — ${data.details}`;
      }

      setTestStatus({
        testing: false,
        success: data.success,
        message: displayMsg,
        latency: data.latency_ms,
      });
    } catch (err: any) {
      console.error("[SettingsModal] Test key network error:", err);
      setTestStatus({
        testing: false,
        success: false,
        message: `Network error: ${err.message || "Failed to reach backend at " + effectiveBackendUrl}`,
      });
    }
  };

  const handleSaveApiSettings = async () => {
    setSaveStatus("Saving...");
    try {
      const personaToSave = personaType === "custom" ? customPersonaText.trim() : personaType;
      const res = await fetch(`${effectiveBackendUrl}/api/v1/settings/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          api_key: apiKey.trim() || undefined,
          model: model.trim() || undefined,
          persona: personaToSave || "natural_human",
        }),
      });

      if (res.ok) {
        setSaveStatus("✓ Settings saved successfully!");
        fetchApiConfig();
        setTimeout(() => setSaveStatus(""), 3500);
      } else {
        const errText = await res.text();
        setSaveStatus(`Failed to save (${res.status}): ${errText.slice(0, 100)}`);
      }
    } catch (err: any) {
      console.error("[SettingsModal] Save key error:", err);
      setSaveStatus(`Error: ${err.message || "Failed to reach backend at " + effectiveBackendUrl}`);
    }
  };

  const handleAddNote = async () => {
    if (!noteContent.trim()) return;
    setAddingNote(true);
    setKnowledgeMessage("");
    try {
      const res = await fetch(`${effectiveBackendUrl}/api/v1/knowledge/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: noteTitle.trim() || "Untitled Note",
          content: noteContent.trim(),
          doc_type: "note",
        }),
      });

      if (res.ok) {
        setNoteTitle("");
        setNoteContent("");
        setKnowledgeMessage("✓ Note added to Knowledge Base!");
        fetchKnowledgeDocs();
        setTimeout(() => setKnowledgeMessage(""), 3000);
      } else {
        const err = await res.json();
        setKnowledgeMessage(`Error: ${err.detail || "Failed to add note"}`);
      }
    } catch (err: any) {
      setKnowledgeMessage(`Error: ${err.message}`);
    } finally {
      setAddingNote(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setKnowledgeMessage("Only PDF files are supported.");
      return;
    }

    setUploading(true);
    setKnowledgeMessage("Extracting and indexing PDF text...");
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${effectiveBackendUrl}/api/v1/knowledge/upload-file`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        setKnowledgeMessage(`✓ "${file.name}" indexed into Knowledge Base!`);
        fetchKnowledgeDocs();
        if (fileInputRef.current) fileInputRef.current.value = "";
        setTimeout(() => setKnowledgeMessage(""), 4000);
      } else {
        const err = await res.json();
        setKnowledgeMessage(`Upload failed: ${err.detail || "Error reading PDF"}`);
      }
    } catch (err: any) {
      setKnowledgeMessage(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (id: string) => {
    try {
      const res = await fetch(`${effectiveBackendUrl}/api/v1/knowledge/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchKnowledgeDocs();
      }
    } catch (err) {
      console.error("Failed to delete document:", err);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await fetch(`${effectiveBackendUrl}/api/v1/knowledge/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery.trim(), limit: 3 }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
      }
    } catch (err) {
      console.error("Search failed:", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="no-drag"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: "16px",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "460px",
          maxHeight: "88vh",
          backgroundColor: "rgba(18, 22, 32, 0.98)",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "12px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 25px 50px rgba(0, 0, 0, 0.8)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px 16px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
            backgroundColor: "rgba(255, 255, 255, 0.03)",
          }}
        >
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span style={{ fontSize: "16px" }}>⚙️</span>
            <span style={{ fontSize: "13px", fontWeight: 600, color: "rgba(230, 237, 243, 0.95)" }}>
              Settings & Knowledge Base
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "rgba(136, 146, 164, 0.7)",
              fontSize: "16px",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {/* Tab Switcher */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            backgroundColor: "rgba(0, 0, 0, 0.2)",
          }}
        >
          <button
            onClick={() => setActiveTab("api")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderBottom: activeTab === "api" ? "2px solid #60a5fa" : "none",
              backgroundColor: activeTab === "api" ? "rgba(96, 165, 250, 0.1)" : "transparent",
              color: activeTab === "api" ? "#60a5fa" : "rgba(136, 146, 164, 0.7)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            🔑 AI & API Keys
          </button>
          <button
            onClick={() => setActiveTab("knowledge")}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderBottom: activeTab === "knowledge" ? "2px solid #34d399" : "none",
              backgroundColor: activeTab === "knowledge" ? "rgba(52, 211, 153, 0.1)" : "transparent",
              color: activeTab === "knowledge" ? "#34d399" : "rgba(136, 146, 164, 0.7)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            📚 Knowledge Base ({documents.length})
          </button>
          <button
            onClick={() => {
              setWinWidth(window.innerWidth);
              setWinHeight(window.innerHeight);
              setActiveTab("window");
            }}
            style={{
              flex: 1,
              padding: "10px",
              border: "none",
              borderBottom: activeTab === "window" ? "2px solid #a78bfa" : "none",
              backgroundColor: activeTab === "window" ? "rgba(167, 139, 250, 0.1)" : "transparent",
              color: activeTab === "window" ? "#a78bfa" : "rgba(136, 146, 164, 0.7)",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            📐 Display & Text Size
          </button>
        </div>

        {/* Content Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "14px" }}>
          {activeTab === "api" && (
            <>
              {/* Active Engine & Model Banner */}
              <div
                style={{
                  backgroundColor: "rgba(37, 99, 235, 0.12)",
                  border: "1px solid rgba(59, 130, 246, 0.3)",
                  borderRadius: "8px",
                  padding: "10px 12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "3px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "11px", fontWeight: 700, color: "#93c5fd", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    CURRENTLY ACTIVE MODEL
                  </span>
                  <span style={{ fontSize: "10px", backgroundColor: "#10b981", color: "#ffffff", padding: "1px 6px", borderRadius: "10px", fontWeight: 600 }}>
                    Active
                  </span>
                </div>
                <div style={{ fontSize: "12px", fontWeight: 600, color: "#ffffff" }}>
                  {provider.toUpperCase()} — {model || "Default Model"}
                </div>
              </div>

              {/* Provider Selection */}
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)", marginBottom: "4px" }}>
                  AI PROVIDER
                </label>
                <select
                  value={provider}
                  onChange={(e) => {
                    const val = e.target.value;
                    setProvider(val);
                    if (val === "huggingface") setModel("deepseek-ai/DeepSeek-R1:fastest");
                    if (val === "nvidia") setModel("meta/llama-3.2-11b-vision-instruct");
                    if (val === "claude") setModel("claude-3-5-sonnet-20241022");
                    if (val === "openai") setModel("gpt-4o-mini");
                    if (val === "gemini") setModel("gemini-1.5-flash");
                  }}
                  style={{
                    width: "100%",
                    backgroundColor: "rgba(0, 0, 0, 0.4)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    color: "rgba(230, 237, 243, 0.95)",
                    fontSize: "12px",
                    outline: "none",
                  }}
                >
                  <option value="nvidia">NVIDIA NIM (Llama 3.2 11B Vision / Instruct)</option>
                  <option value="huggingface">Hugging Face Router (DeepSeek-R1 Fastest)</option>
                  <option value="claude">Anthropic Claude (Claude 3.5 Sonnet)</option>
                  <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
                  <option value="gemini">Google Gemini (Gemini 1.5 Flash)</option>
                </select>
              </div>

              {/* API Key Input */}
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)", marginBottom: "4px" }}>
                  API KEY
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={
                    configuredProviders[provider]?.configured
                      ? `•••••••• (Saved: ${configuredProviders[provider].preview})`
                      : `Enter your ${provider.toUpperCase()} API key...`
                  }
                  style={{
                    width: "100%",
                    backgroundColor: "rgba(0, 0, 0, 0.4)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    color: "rgba(230, 237, 243, 0.95)",
                    fontSize: "12px",
                    outline: "none",
                  }}
                />
              </div>

              {/* Model Input */}
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)", marginBottom: "4px" }}>
                  MODEL ID
                </label>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. claude-3-5-sonnet-20241022 or gpt-4o-mini"
                  style={{
                    width: "100%",
                    backgroundColor: "rgba(0, 0, 0, 0.4)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    color: "rgba(230, 237, 243, 0.95)",
                    fontSize: "12px",
                    outline: "none",
                  }}
                />
              </div>

              {/* AI Persona & Voice Tone Input */}
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)", marginBottom: "4px" }}>
                  AI PERSONA & SOUND (HOW ANSWERS SHOULD SOUND)
                </label>
                <select
                  value={personaType}
                  onChange={(e) => setPersonaType(e.target.value)}
                  style={{
                    width: "100%",
                    backgroundColor: "rgba(0, 0, 0, 0.4)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    color: "rgba(230, 237, 243, 0.95)",
                    fontSize: "12px",
                    outline: "none",
                    marginBottom: personaType === "custom" ? "8px" : "0",
                  }}
                >
                  <option value="natural_human">🗣️ Like Human (Authentic, natural, articulate, warm)</option>
                  <option value="concise">⚡ Short & Crisp (Direct bullet points, 2-3 sentences)</option>
                  <option value="interview_star">💼 Interview STAR Method (Situation, Task, Action, Result)</option>
                  <option value="technical">🛠️ Technical Deep-Dive (Architecture, trade-offs, code)</option>
                  <option value="custom">✍️ Custom Instructions (Type your own preference)...</option>
                </select>
                {personaType === "custom" && (
                  <textarea
                    rows={2}
                    value={customPersonaText}
                    onChange={(e) => setCustomPersonaText(e.target.value)}
                    placeholder="e.g. Sound like a senior tech lead: direct, pragmatic, concise, and human-like..."
                    style={{
                      width: "100%",
                      backgroundColor: "rgba(0, 0, 0, 0.5)",
                      border: "1px solid rgba(96, 165, 250, 0.4)",
                      borderRadius: "6px",
                      padding: "8px 10px",
                      color: "rgba(230, 237, 243, 0.95)",
                      fontSize: "12px",
                      outline: "none",
                      resize: "none",
                    }}
                  />
                )}
              </div>

              {/* Actions: Test Connection & Save */}
              <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
                <button
                  onClick={handleTestConnection}
                  disabled={testStatus.testing}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "1px solid rgba(96, 165, 250, 0.4)",
                    backgroundColor: "rgba(96, 165, 250, 0.15)",
                    color: "#93c5fd",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: testStatus.testing ? "default" : "pointer",
                  }}
                >
                  {testStatus.testing ? "Testing..." : "⚡ Test Connection"}
                </button>
                <button
                  onClick={handleSaveApiSettings}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor: "#2563eb",
                    color: "#ffffff",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Save Settings
                </button>
              </div>

              {/* Status messages */}
              {testStatus.message && (
                <div
                  style={{
                    padding: "8px 10px",
                    borderRadius: "6px",
                    fontSize: "11px",
                    backgroundColor:
                      testStatus.success === true
                        ? "rgba(16, 185, 129, 0.15)"
                        : testStatus.success === false
                        ? "rgba(239, 68, 68, 0.15)"
                        : "rgba(255, 255, 255, 0.05)",
                    color:
                      testStatus.success === true
                        ? "#34d399"
                        : testStatus.success === false
                        ? "#f87171"
                        : "rgba(230, 237, 243, 0.8)",
                    border: `1px solid ${
                      testStatus.success === true
                        ? "rgba(16, 185, 129, 0.3)"
                        : testStatus.success === false
                        ? "rgba(239, 68, 68, 0.3)"
                        : "transparent"
                    }`,
                  }}
                >
                  {testStatus.message}
                </div>
              )}

              {saveStatus && (
                <div style={{ fontSize: "11px", color: saveStatus.startsWith("✓") ? "#34d399" : "#f87171", textAlign: "center" }}>
                  {saveStatus}
                </div>
              )}
            </>
          )}

          {activeTab === "knowledge" && (
            <>
              {/* PDF Upload Section */}
              <div
                style={{
                  padding: "10px",
                  borderRadius: "8px",
                  border: "1px dashed rgba(255, 255, 255, 0.2)",
                  backgroundColor: "rgba(0, 0, 0, 0.2)",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "6px",
                  textAlign: "center",
                }}
              >
                <span style={{ fontSize: "18px" }}>📄</span>
                <span style={{ fontSize: "12px", color: "rgba(230, 237, 243, 0.9)", fontWeight: 500 }}>
                  Upload Resume or Project Document (PDF)
                </span>
                <span style={{ fontSize: "10px", color: "rgba(136, 146, 164, 0.6)" }}>
                  Instant text extraction & fast local SQLite FTS5 search
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileUpload}
                  style={{ display: "none" }}
                  id="pdf-upload"
                  disabled={uploading}
                />
                <label
                  htmlFor="pdf-upload"
                  style={{
                    marginTop: "4px",
                    padding: "4px 12px",
                    borderRadius: "4px",
                    backgroundColor: "rgba(52, 211, 153, 0.2)",
                    border: "1px solid rgba(52, 211, 153, 0.4)",
                    color: "#34d399",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: uploading ? "default" : "pointer",
                  }}
                >
                  {uploading ? "Extracting..." : "Choose PDF File"}
                </label>
              </div>

              {/* Add Text Note / Details */}
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)" }}>
                  ADD PERSONAL DETAILS / TEXT NOTE
                </span>
                <input
                  type="text"
                  placeholder="Title (e.g. Work Experience, Skills, Project A)"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  style={{
                    backgroundColor: "rgba(0, 0, 0, 0.4)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    color: "rgba(230, 237, 243, 0.9)",
                    fontSize: "11px",
                    outline: "none",
                  }}
                />
                <textarea
                  placeholder="Paste details, bullet points, STAR interview answers, or achievements..."
                  rows={3}
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  style={{
                    backgroundColor: "rgba(0, 0, 0, 0.4)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    color: "rgba(230, 237, 243, 0.9)",
                    fontSize: "11px",
                    outline: "none",
                    resize: "vertical",
                  }}
                />
                <button
                  onClick={handleAddNote}
                  disabled={!noteContent.trim() || addingNote}
                  style={{
                    alignSelf: "flex-end",
                    padding: "4px 12px",
                    borderRadius: "4px",
                    backgroundColor: noteContent.trim() ? "rgba(59, 130, 246, 0.85)" : "rgba(255, 255, 255, 0.08)",
                    border: "none",
                    color: "#ffffff",
                    fontSize: "11px",
                    fontWeight: 500,
                    cursor: noteContent.trim() ? "pointer" : "default",
                  }}
                >
                  {addingNote ? "Saving..." : "Save to Knowledge Base"}
                </button>
              </div>

              {knowledgeMessage && (
                <div style={{ fontSize: "11px", color: knowledgeMessage.startsWith("✓") ? "#34d399" : "#f87171" }}>
                  {knowledgeMessage}
                </div>
              )}

              {/* Indexed Documents List */}
              <div>
                <span style={{ fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)", display: "block", marginBottom: "6px" }}>
                  INDEXED DOCUMENTS ({documents.length})
                </span>
                {documents.length === 0 ? (
                  <div style={{ fontSize: "11px", color: "rgba(136, 146, 164, 0.5)", fontStyle: "italic" }}>
                    No documents yet. Upload a PDF or add a text note above.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "140px", overflowY: "auto" }}>
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "6px 10px",
                          borderRadius: "6px",
                          backgroundColor: "rgba(255, 255, 255, 0.04)",
                          border: "1px solid rgba(255, 255, 255, 0.06)",
                        }}
                      >
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span style={{ fontSize: "11px", fontWeight: 600, color: "rgba(230, 237, 243, 0.9)" }}>
                            {doc.doc_type === "pdf" ? "📄" : "📝"} {doc.title}
                          </span>
                          <span style={{ fontSize: "9px", color: "rgba(136, 146, 164, 0.6)" }}>
                            {doc.word_count} words • {new Date(doc.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "rgba(248, 113, 113, 0.7)",
                            fontSize: "11px",
                            cursor: "pointer",
                          }}
                          title="Delete from knowledge base"
                        >
                          🗑️
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Search Tester */}
              <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "10px" }}>
                <span style={{ fontSize: "10px", fontWeight: 600, color: "rgba(136, 146, 164, 0.7)", textTransform: "uppercase", display: "block", marginBottom: "4px" }}>
                  Test Knowledge Search (Sub-5ms FTS5)
                </span>
                <div style={{ display: "flex", gap: "6px" }}>
                  <input
                    type="text"
                    placeholder="Search keywords (e.g. Python, Docker, Leader)..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    style={{
                      flex: 1,
                      backgroundColor: "rgba(0, 0, 0, 0.4)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "6px",
                      padding: "6px 8px",
                      color: "rgba(230, 237, 243, 0.9)",
                      fontSize: "11px",
                      outline: "none",
                    }}
                  />
                  <button
                    onClick={handleSearch}
                    style={{
                      padding: "6px 10px",
                      borderRadius: "6px",
                      border: "none",
                      backgroundColor: "rgba(255, 255, 255, 0.08)",
                      color: "rgba(230, 237, 243, 0.8)",
                      fontSize: "11px",
                      cursor: "pointer",
                    }}
                  >
                    Search
                  </button>
                </div>
                {searchResults.length > 0 && (
                  <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "4px" }}>
                    {searchResults.map((r, i) => (
                      <div key={i} style={{ fontSize: "10px", padding: "4px 6px", backgroundColor: "rgba(0,0,0,0.3)", borderRadius: "4px", color: "rgba(180, 190, 205, 0.9)" }}>
                        <strong style={{ color: "#34d399" }}>[{r.title}]: </strong>
                        <span>{r.snippet || r.content_chunk}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {activeTab === "window" && (
            <>
              {/* Text Size / Typography Section */}
              <div
                style={{
                  padding: "12px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(96, 165, 250, 0.08)",
                  border: "1px solid rgba(96, 165, 250, 0.25)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: "12px", fontWeight: 600, color: "#93c5fd" }}>
                      🔤 Text & Font Size
                    </div>
                    <div style={{ fontSize: "11px", color: "rgba(180, 190, 205, 0.8)" }}>
                      Scale teleprompter reading size & chat messages
                    </div>
                  </div>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: "#60a5fa", backgroundColor: "rgba(0,0,0,0.4)", padding: "2px 8px", borderRadius: "4px" }}>
                    {currentFontSize} px
                  </span>
                </div>

                {/* Live Text Preview Box */}
                <div
                  style={{
                    padding: "8px 10px",
                    borderRadius: "6px",
                    backgroundColor: "rgba(0, 0, 0, 0.45)",
                    border: "1px dashed rgba(255, 255, 255, 0.15)",
                    fontSize: `${currentFontSize}px`,
                    color: "rgba(230, 237, 243, 0.95)",
                    lineHeight: "1.4",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  <span style={{ color: "#34d399", fontWeight: 600 }}>🎙️ Interviewer: </span>
                  <span>Can you explain your system architecture?</span>
                </div>

                {/* Font Size Quick Presets */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "6px" }}>
                  {[
                    { label: "Small", size: 11 },
                    { label: "Default", size: 13 },
                    { label: "Medium", size: 15 },
                    { label: "Large", size: 18 },
                    { label: "Huge", size: 22 },
                  ].map((p) => {
                    const isSelected = currentFontSize === p.size;
                    return (
                      <button
                        key={p.label}
                        onClick={() => setFontSize(p.size)}
                        style={{
                          padding: "6px 2px",
                          borderRadius: "6px",
                          border: `1px solid ${isSelected ? "#60a5fa" : "rgba(255, 255, 255, 0.1)"}`,
                          backgroundColor: isSelected ? "rgba(96, 165, 250, 0.25)" : "rgba(0, 0, 0, 0.3)",
                          color: isSelected ? "#ffffff" : "rgba(203, 213, 225, 0.8)",
                          cursor: "pointer",
                          textAlign: "center",
                          fontSize: "11px",
                          fontWeight: isSelected ? 600 : 400,
                        }}
                      >
                        <div>{p.label}</div>
                        <div style={{ fontSize: "9px", opacity: 0.75 }}>{p.size}px</div>
                      </button>
                    );
                  })}
                </div>

                {/* Text Size Slider */}
                <div>
                  <input
                    type="range"
                    min="10"
                    max="26"
                    step="1"
                    value={currentFontSize}
                    onChange={(e) => setFontSize(Number(e.target.value))}
                    style={{ width: "100%", accentColor: "#60a5fa", cursor: "pointer" }}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", color: "rgba(148, 163, 184, 0.7)", marginTop: "2px" }}>
                    <span>10px (Compact)</span>
                    <span>13px (Default)</span>
                    <span>26px (Maximum)</span>
                  </div>
                </div>
              </div>

              {/* Dimensions Summary */}
              <div
                style={{
                  padding: "12px",
                  borderRadius: "8px",
                  backgroundColor: "rgba(167, 139, 250, 0.08)",
                  border: "1px solid rgba(167, 139, 250, 0.2)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: "12px", fontWeight: 600, color: "#c4b5fd" }}>
                    Overlay Window Size
                  </div>
                  <div style={{ fontSize: "11px", color: "rgba(180, 190, 205, 0.8)" }}>
                    Current Dimensions: <strong style={{ color: "#ffffff" }}>{winWidth}px × {winHeight}px</strong>
                  </div>
                </div>
                <span style={{ fontSize: "20px" }}>📐</span>
              </div>

              {/* Quick Size Presets */}
              <div>
                <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)", marginBottom: "8px" }}>
                  QUICK SIZE PRESETS
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  {[
                    { label: "Compact", w: 380, h: 480, desc: "Minimal footprint" },
                    { label: "Standard", w: 460, h: 540, desc: "Balanced view" },
                    { label: "Wide", w: 560, h: 540, desc: "Extra horizontal space" },
                    { label: "Large", w: 620, h: 680, desc: "Extended interview feed" },
                  ].map((p) => {
                    const isActive = winWidth === p.w && winHeight === p.h;
                    return (
                      <button
                        key={p.label}
                        onClick={() => applyWindowSize(p.w, p.h)}
                        style={{
                          padding: "10px",
                          borderRadius: "6px",
                          border: `1px solid ${isActive ? "#a78bfa" : "rgba(255, 255, 255, 0.1)"}`,
                          backgroundColor: isActive ? "rgba(167, 139, 250, 0.2)" : "rgba(0, 0, 0, 0.3)",
                          color: isActive ? "#ffffff" : "rgba(230, 237, 243, 0.9)",
                          cursor: "pointer",
                          textAlign: "left",
                        }}
                      >
                        <div style={{ fontSize: "12px", fontWeight: 600 }}>{p.label}</div>
                        <div style={{ fontSize: "10px", color: "rgba(148, 163, 184, 0.8)" }}>
                          {p.w} × {p.h}px • {p.desc}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Custom Width Slider */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <label style={{ fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)" }}>
                    CUSTOM WIDTH
                  </label>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#60a5fa" }}>{winWidth} px</span>
                </div>
                <input
                  type="range"
                  min="320"
                  max="900"
                  step="10"
                  value={winWidth}
                  onChange={(e) => applyWindowSize(Number(e.target.value), winHeight)}
                  style={{ width: "100%", accentColor: "#60a5fa", cursor: "pointer" }}
                />
              </div>

              {/* Custom Height Slider */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                  <label style={{ fontSize: "11px", fontWeight: 600, color: "rgba(136, 146, 164, 0.8)" }}>
                    CUSTOM HEIGHT
                  </label>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#34d399" }}>{winHeight} px</span>
                </div>
                <input
                  type="range"
                  min="240"
                  max="900"
                  step="10"
                  value={winHeight}
                  onChange={(e) => applyWindowSize(winWidth, Number(e.target.value))}
                  style={{ width: "100%", accentColor: "#34d399", cursor: "pointer" }}
                />
              </div>

              {/* Drag Handle Tip */}
              <div
                style={{
                  padding: "10px",
                  borderRadius: "6px",
                  backgroundColor: "rgba(255, 255, 255, 0.04)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  fontSize: "11px",
                  color: "rgba(203, 213, 225, 0.9)",
                  lineHeight: "1.4",
                }}
              >
                💡 <strong>Freeform Resizing:</strong> You can also drag the bottom-right corner grip handle <strong>↘</strong> directly on the overlay to resize width and height freely at any moment.
              </div>

              {/* Stealth & Invisibility Status */}
              <div
                style={{
                  padding: "10px",
                  borderRadius: "6px",
                  backgroundColor: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.2)",
                  fontSize: "11px",
                  color: "#a7f3d0",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <div style={{ fontWeight: 600, color: "#34d399", marginBottom: "2px" }}>
                  🛡️ Stealth & Invisibility Active:
                </div>
                <div>✓ <strong>Alt + Tab:</strong> Excluded (Win32 Tool Window)</div>
                <div>✓ <strong>Win + Tab (Task View):</strong> Excluded</div>
                <div>✓ <strong>Windows Taskbar:</strong> Excluded</div>
                <div>✓ <strong>Task Manager:</strong> Excluded from "Apps" list</div>
                <div>✓ <strong>Screen Share Protection:</strong> Excluded from Zoom, Meet, Teams, Discord</div>
                <div>✓ <strong>Zero CMD:</strong> Command prompt window completely hidden</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
