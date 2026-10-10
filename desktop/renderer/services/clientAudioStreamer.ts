/**
 * Client Audio & Speech Streaming Service
 * Captures microphone audio directly in the client Electron browser window
 * and streams speech transcripts and PCM audio chunks to the backend.
 * 
 * Features:
 * 1. Web Speech API (webkitSpeechRecognition) for instant real-time transcription on client PC.
 * 2. Web Audio API (getUserMedia + ScriptProcessor/AudioWorklet) for real-time RMS/VAD calculation and PCM audio streaming.
 * 3. Graceful fallback and auto-recovery.
 */

import { useAudioStore, useTranscriptStore, useLicenseStore } from "../stores";

export type SendCommandFn = (type: string, payload?: Record<string, unknown>) => void;

class ClientAudioStreamer {
  private isStreaming = false;
  private sendCommand: SendCommandFn | null = null;

  // Web Speech API
  private recognition: any = null;
  private isRecognitionRunning = false;
  private lastFinalTranscript = "";
  private lastFinalTime = 0;

  // Web Audio API
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private gainNode: GainNode | null = null;

  // VAD & Frame Buffering
  private silenceFramesCount = 0;
  private speechFramesBuffer: Float32Array[] = [];
  private isVadSpeaking = false;

  public start(sendCommand: SendCommandFn) {
    if (this.isStreaming) return;

    const { isBlocked } = useLicenseStore.getState();
    if (isBlocked) {
      console.warn("[ClientAudio] Cannot start audio streaming: license is blocked");
      return;
    }

    this.isStreaming = true;
    this.sendCommand = sendCommand;
    console.log("[ClientAudio] Starting client audio capture & speech recognition...");

    // 1. Start Web Speech Recognition
    this.initSpeechRecognition();

    // 2. Start Web Audio Microphone capture & VAD
    this.initWebAudio();
  }

  public stop() {
    if (!this.isStreaming) return;
    this.isStreaming = false;
    console.log("[ClientAudio] Stopping client audio capture...");

    // Stop Speech Recognition
    if (this.recognition) {
      try {
        this.recognition.onend = null;
        this.recognition.onerror = null;
        this.recognition.onresult = null;
        this.recognition.stop();
      } catch (e) {
        // ignore
      }
      this.recognition = null;
      this.isRecognitionRunning = false;
    }

    // Stop Web Audio
    if (this.processorNode) {
      try {
        this.processorNode.disconnect();
      } catch (e) {}
      this.processorNode = null;
    }

    if (this.gainNode) {
      try {
        this.gainNode.disconnect();
      } catch (e) {}
      this.gainNode = null;
    }

    if (this.sourceNode) {
      try {
        this.sourceNode.disconnect();
      } catch (e) {}
      this.sourceNode = null;
    }

    if (this.audioContext && this.audioContext.state !== "closed") {
      try {
        this.audioContext.close();
      } catch (e) {}
      this.audioContext = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }

    this.speechFramesBuffer = [];
    this.silenceFramesCount = 0;
    this.isVadSpeaking = false;
    useAudioStore.getState().setVadState("interviewer", "SILENCE");
  }

  public isActive(): boolean {
    return this.isStreaming;
  }

  /**
   * Interrupt and reset: immediately drops previous speech buffers, stops any
   * pending transcripts, clears VAD, purges Chromium speech queue, and sends
   * command.stop_and_reset to backend so it immediately listens fresh for new talks.
   */
  public interruptAndReset() {
    console.log("[ClientAudio] Interrupting previous audio data & resetting listener...");

    // 1. Clear audio buffers and speech deduplication
    this.speechFramesBuffer = [];
    this.silenceFramesCount = 0;
    this.isVadSpeaking = false;
    this.lastFinalTranscript = "";
    this.lastFinalTime = 0;

    useAudioStore.getState().setVadState("interviewer", "SILENCE");
    useTranscriptStore.getState().setPartialText("");

    // 2. Completely destroy speech recognition instance to purge any buffered sentences
    if (this.recognition) {
      try {
        this.recognition.onstart = null;
        this.recognition.onresult = null;
        this.recognition.onerror = null;
        this.recognition.onend = null;
        this.recognition.abort();
      } catch (e) {}
      this.recognition = null;
      this.isRecognitionRunning = false;
    }

    // 3. Send command to backend
    if (this.sendCommand) {
      this.sendCommand("command.stop_and_reset");
    }

    // 4. Restart fresh SpeechRecognition instance cleanly after 120ms
    setTimeout(() => {
      if (this.isStreaming) {
        this.initSpeechRecognition();
      }
    }, 120);
  }

  /**
   * Initializes Web Speech API (webkitSpeechRecognition) for zero-latency client-side speech-to-text.
   */
  private initSpeechRecognition() {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn("[ClientAudio] Web Speech API not supported in this Chromium context; using Web Audio fallback");
      return;
    }

    try {
      const rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = "en-US";
      rec.maxAlternatives = 1;

      rec.onstart = () => {
        this.isRecognitionRunning = true;
        console.log("[ClientAudio] Web Speech Recognition active");
      };

      rec.onresult = (event: any) => {
        if (!this.isStreaming) return;

        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const item = event.results[i];
          const transcript = item[0]?.transcript || "";

          if (item.isFinal) {
            const clean = transcript.trim();
            if (clean.length >= 3) {
              const now = Date.now();
              const norm = clean.toLowerCase().replace(/[^\w\s]/g, "").trim();
              const lastNorm = this.lastFinalTranscript.toLowerCase().replace(/[^\w\s]/g, "").trim();

              // Deduplicate if identical within 3.5s
              if (norm !== lastNorm || now - this.lastFinalTime > 3500) {
                this.lastFinalTranscript = clean;
                this.lastFinalTime = now;
                console.log("[ClientAudio] Speech final:", clean);

                // Send to backend to trigger AI co-pilot response and broadcast speech.final
                if (this.sendCommand) {
                  this.sendCommand("command.speech_input", {
                    text: clean,
                    speaker: "interviewer",
                  });
                }

                useTranscriptStore.getState().setPartialText("");
              }
            }
          } else {
            interimText += transcript;
          }
        }

        if (interimText.trim()) {
          useTranscriptStore.getState().setPartialText(interimText, "interviewer");
          if (this.sendCommand) {
            this.sendCommand("command.speech_partial", {
              text: interimText,
              speaker: "interviewer",
            });
          }
        }
      };

      rec.onerror = (err: any) => {
        console.debug("[ClientAudio] Speech recognition notice:", err?.error);
        if (err?.error === "not-allowed" || err?.error === "service-not-allowed") {
          console.warn("[ClientAudio] Speech recognition permission denied or service unavailable");
        }
      };

      rec.onend = () => {
        this.isRecognitionRunning = false;
        if (this.isStreaming) {
          // Restart continuously
          setTimeout(() => {
            if (this.isStreaming && !this.isRecognitionRunning) {
              try {
                rec.start();
              } catch (e) {
                // ignore
              }
            }
          }, 200);
        }
      };

      rec.start();
      this.recognition = rec;
    } catch (e) {
      console.warn("[ClientAudio] Failed to initialize Web Speech API:", e);
    }
  }

  /**
   * Initializes Web Audio microphone capture, calculates RMS for real-time VAD,
   * and streams PCM16 audio chunks to backend for faster-whisper/Google STT.
   */
  private async initWebAudio() {
    if (!navigator?.mediaDevices?.getUserMedia) {
      console.warn("[ClientAudio] navigator.mediaDevices.getUserMedia not available");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      if (!this.isStreaming) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      this.mediaStream = stream;

      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      this.audioContext = new AudioCtx({ sampleRate: 16000 });

      this.sourceNode = this.audioContext.createMediaStreamSource(stream);
      this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);

      // GainNode with gain = 0 prevents microphone audio from playing through speakers (echo loop)
      this.gainNode = this.audioContext.createGain();
      this.gainNode.gain.value = 0;

      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.gainNode);
      this.gainNode.connect(this.audioContext.destination);

      this.processorNode.onaudioprocess = (e: AudioProcessingEvent) => {
        if (!this.isStreaming) return;

        const inputBuffer = e.inputBuffer.getChannelData(0);
        let sum = 0;
        for (let i = 0; i < inputBuffer.length; i++) {
          sum += inputBuffer[i] * inputBuffer[i];
        }
        const rms = Math.sqrt(sum / inputBuffer.length);

        // VAD Threshold (~0.015)
        const isSpeaking = rms >= 0.015;

        if (isSpeaking) {
          this.silenceFramesCount = 0;
          this.speechFramesBuffer.push(new Float32Array(inputBuffer));

          if (!this.isVadSpeaking) {
            this.isVadSpeaking = true;
            useAudioStore.getState().setVadState("interviewer", "SPEAKING");
            if (this.sendCommand) {
              this.sendCommand("command.client_vad_state", {
                speaker: "interviewer",
                state: "SPEAKING",
              });
            }
          }

          // If speech is long and continuous (> 4.5 seconds = 18 frames of 4096 at 16kHz)
          if (this.speechFramesBuffer.length >= 18) {
            this.flushSpeechBuffer();
          }
        } else {
          this.silenceFramesCount++;

          // After 5 frames (~1.25s) of silence following speech
          if (this.silenceFramesCount >= 5 && this.isVadSpeaking) {
            this.isVadSpeaking = false;
            useAudioStore.getState().setVadState("interviewer", "SILENCE");
            if (this.sendCommand) {
              this.sendCommand("command.client_vad_state", {
                speaker: "interviewer",
                state: "SILENCE",
              });
            }

            // If we have collected enough audio (at least 0.75s of speech)
            if (this.speechFramesBuffer.length >= 3) {
              this.flushSpeechBuffer();
            } else {
              this.speechFramesBuffer = [];
            }
          }
        }
      };

      console.log("[ClientAudio] Web Audio microphone stream & VAD processor ready");
    } catch (err) {
      console.error("[ClientAudio] Failed to access client microphone via getUserMedia:", err);
    }
  }

  /**
   * Concatenates captured float32 audio frames, converts to PCM16, and sends to backend.
   * Only used if browser SpeechRecognition is unavailable or failing.
   */
  private flushSpeechBuffer() {
    if (this.speechFramesBuffer.length === 0) return;

    // If SpeechRecognition is running, it already handles real-time transcription directly.
    // Do NOT stream audio chunks to avoid duplicate server transcription.
    if (this.isRecognitionRunning || this.recognition) {
      this.speechFramesBuffer = [];
      return;
    }

    try {
      const totalSamples = this.speechFramesBuffer.reduce((acc, f) => acc + f.length, 0);
      const merged = new Float32Array(totalSamples);
      let offset = 0;
      for (const frame of this.speechFramesBuffer) {
        merged.set(frame, offset);
        offset += frame.length;
      }
      this.speechFramesBuffer = [];

      // Convert Float32 [-1.0, 1.0] to signed Int16 PCM
      const pcm16 = new Int16Array(totalSamples);
      for (let i = 0; i < totalSamples; i++) {
        const s = Math.max(-1, Math.min(1, merged[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      // Convert Int16 buffer to Base64
      const uint8 = new Uint8Array(pcm16.buffer);
      let binary = "";
      const chunkSize = 8192;
      for (let i = 0; i < uint8.length; i += chunkSize) {
        binary += String.fromCharCode.apply(null, uint8.subarray(i, i + chunkSize) as any);
      }
      const base64Data = btoa(binary);

      if (this.sendCommand) {
        this.sendCommand("command.audio_chunk", {
          data: base64Data,
          speaker: "interviewer",
          sample_rate: 16000,
        });
      }
    } catch (err) {
      console.error("[ClientAudio] Error flushing speech audio buffer:", err);
    }
  }
}

export const clientAudioStreamer = new ClientAudioStreamer();
