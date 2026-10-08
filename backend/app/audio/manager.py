"""
Audio stream manager using PyAudioWPatch for reliable Windows WASAPI loopback
and microphone capture with dual-stream speaker separation and real-time VAD.
"""

import asyncio
import time
from typing import Callable, Optional, Dict, Any, List
import numpy as np

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None

from app.audio.types import AudioSourceType, VADState, AudioChunk, AudioDevice, SpeakerRole
from app.audio.devices import AudioDeviceManager
from app.audio.processor import AudioProcessor
from app.audio.vad import VoiceActivityDetector
from app.audio.buffer import AudioBuffer
from app.stt.transcriber import get_transcriber, LocalTranscriber
from app.logging.logger import get_logger

logger = get_logger(__name__)


class AudioManager:
    """
    Manages dual-stream audio capture:
    - SYSTEM: Interviewer / remote party via WASAPI loopback
    - MICROPHONE: Interviewee / local user
    - BOTH: Simultaneous dual-stream capture with speaker diarization
    """

    def __init__(
        self,
        event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        on_speech_final: Optional[Callable[[SpeakerRole, str], Any]] = None,
        target_sample_rate: int = 16000,
        chunk_duration_ms: int = 50,
    ):
        self.event_callback = event_callback
        self.on_speech_final = on_speech_final
        self.processor = AudioProcessor(target_sample_rate=target_sample_rate)
        self.buffer = AudioBuffer(max_chunks=400)

        # Independent VADs for Interviewer (System) and Interviewee (Mic)
        self.vad_interviewer = VoiceActivityDetector()
        self.vad_interviewee = VoiceActivityDetector()

        # Buffers for collecting continuous speech audio frames for STT
        self.speech_frames: Dict[str, List[np.ndarray]] = {
            "interviewer": [],
            "interviewee": [],
        }
        self._last_partial_time: Dict[str, float] = {"interviewer": 0.0, "interviewee": 0.0}
        self._partial_busy: Dict[str, bool] = {"interviewer": False, "interviewee": False}

        self.target_sample_rate = target_sample_rate
        self.chunk_duration_ms = chunk_duration_ms

        self.is_capturing = False
        self.current_source: AudioSourceType = AudioSourceType.BOTH

        self.pa: Optional[pyaudio.PyAudio] = None
        self.stream_system = None
        self.stream_mic = None

        self.device_system_name: Optional[str] = None
        self.device_mic_name: Optional[str] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _make_callback(self, speaker: SpeakerRole, vad: VoiceActivityDetector, orig_sr: int, channels: int):
        """Factory creating dedicated audio callbacks tagged by speaker."""
        pre_roll: List[np.ndarray] = []

        def callback(in_data, frame_count, time_info, status):
            if not self.is_capturing:
                abort_status = getattr(pyaudio, "paAbort", 1) if pyaudio else 1
                return (None, abort_status)

            try:
                audio_np = np.frombuffer(in_data, dtype=np.float32)
                if channels > 1:
                    audio_np = audio_np.reshape(-1, channels)

                resampled_f32, pcm16_bytes, rms = self.processor.process(audio_np, orig_sr=orig_sr)
                vad_state, state_changed = vad.update(rms)
                is_speech = vad_state in (VADState.SPEECH_STARTED, VADState.SPEAKING, VADState.POSSIBLE_END)

                chunk = AudioChunk(
                    data=pcm16_bytes,
                    sample_rate=self.target_sample_rate,
                    channels=1,
                    timestamp=time.time(),
                    source=self.current_source,
                    rms_energy=rms,
                    is_speech=is_speech,
                    speaker=speaker,
                )
                self.buffer.push(chunk)

                # Keep short pre-roll of recent silence frames (~150ms)
                if not is_speech:
                    pre_roll.append(resampled_f32)
                    if len(pre_roll) > 5:
                        pre_roll.pop(0)

                # Collect speech frames for transcription while speech is ongoing
                if is_speech:
                    if vad_state == VADState.SPEECH_STARTED and pre_roll:
                        self.speech_frames[speaker].extend(pre_roll)
                        pre_roll.clear()

                    self.speech_frames[speaker].append(resampled_f32)
                    now_ts = time.time()

                    # Emit partial transcription every ~0.5s
                    if (
                        now_ts - self._last_partial_time.get(speaker, 0.0) >= 0.5
                        and not self._partial_busy.get(speaker, False)
                        and len(self.speech_frames[speaker]) >= 4
                        and self._loop
                        and self._loop.is_running()
                    ):
                        self._last_partial_time[speaker] = now_ts
                        self._partial_busy[speaker] = True
                        partial_audio = np.concatenate(self.speech_frames[speaker])
                        asyncio.run_coroutine_threadsafe(
                            self._transcribe_partial(speaker, partial_audio),
                            self._loop,
                        )

                    # Auto-segment long continuous speech (every 4.5 seconds) so responses stay live
                    current_samples = sum(len(f) for f in self.speech_frames[speaker])
                    if current_samples >= 16000 * 4.5:
                        frames = self.speech_frames[speaker]
                        self.speech_frames[speaker] = []
                        self._partial_busy[speaker] = False
                        if frames and self._loop and self._loop.is_running():
                            total_audio = np.concatenate(frames)
                            asyncio.run_coroutine_threadsafe(
                                self._transcribe_and_dispatch(speaker, total_audio),
                                self._loop,
                            )

                elif vad_state == VADState.SPEECH_ENDED:
                    # Speech segment concluded (pause/gap detected) — trigger final transcription
                    frames = self.speech_frames[speaker]
                    self.speech_frames[speaker] = []
                    self._partial_busy[speaker] = False
                    if frames and self.is_capturing:
                        total_audio = np.concatenate(frames)
                        # Require at least 0.15s of audio (2400 samples at 16kHz)
                        if len(total_audio) >= 2400 and self._loop and self._loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                self._transcribe_and_dispatch(speaker, total_audio),
                                self._loop,
                            )

                if state_changed and self.event_callback and self._loop and self._loop.is_running() and self.is_capturing:
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_event(
                            "audio.vad_state_changed",
                            {"speaker": speaker, "state": vad_state.value, "rms": rms},
                        ),
                        self._loop,
                    )
            except Exception as e:
                logger.error("Error in audio stream callback", speaker=speaker, error=str(e))

            abort_status = getattr(pyaudio, "paAbort", 1) if pyaudio else 1
            cont_status = getattr(pyaudio, "paContinue", 0) if pyaudio else 0
            return (None, cont_status if self.is_capturing else abort_status)

        return callback

    async def _transcribe_partial(self, speaker: SpeakerRole, audio_data: np.ndarray) -> None:
        """Run quick partial speech-to-text in worker thread and emit speech.partial event."""
        if not self.is_capturing:
            self._partial_busy[speaker] = False
            return
        try:
            transcriber = get_transcriber()
            text = await asyncio.to_thread(transcriber.transcribe, audio_data)
            if not self.is_capturing:
                return
            text = text.strip()
            if text:
                await self._dispatch_event(
                    "speech.partial",
                    {
                        "speaker": speaker,
                        "text": text,
                    },
                )
        except Exception as e:
            logger.debug("Partial transcription notice", speaker=speaker, error=str(e))
        finally:
            self._partial_busy[speaker] = False

    async def _transcribe_and_dispatch(self, speaker: SpeakerRole, audio_data: np.ndarray) -> None:
        """Run fast speech-to-text in worker thread and emit speech.final event."""
        if not self.is_capturing:
            return
        try:
            transcriber = get_transcriber()
            text = await asyncio.to_thread(transcriber.transcribe, audio_data)
            if not self.is_capturing:
                return
            text = text.strip()
            if not text:
                return

            logger.info("Transcribed speech segment", speaker=speaker, text=text)

            # Broadcast speech.final event
            await self._dispatch_event(
                "speech.final",
                {
                    "speaker": speaker,
                    "text": text,
                    "confidence": 0.95,
                },
            )

            # Invoke custom speech callback if configured
            if self.on_speech_final:
                try:
                    res = self.on_speech_final(speaker, text)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    logger.error("Error in on_speech_final handler", error=str(e))

        except Exception as e:
            logger.error("Failed to transcribe speech audio", speaker=speaker, error=str(e))

    async def _dispatch_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Send an audio event to the application bus."""
        if self.event_callback:
            try:
                res = self.event_callback(event_type, payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error("Failed to dispatch audio event", event=event_type, error=str(e))

    async def start(
        self,
        source: AudioSourceType = AudioSourceType.BOTH,
        device_id: Optional[int] = None,
    ) -> bool:
        """Start capturing audio with dual-stream speaker separation."""
        if self.is_capturing:
            await self.stop()

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self.current_source = source
        self.pa = pyaudio.PyAudio()

        self.speech_frames["interviewer"] = []
        self.speech_frames["interviewee"] = []
        self._partial_busy["interviewer"] = False
        self._partial_busy["interviewee"] = False
        self.vad_interviewer.reset()
        self.vad_interviewee.reset()
        self.is_capturing = True

        started_system = False
        started_mic = False

        # 1. Setup Interviewer stream (System Audio via WASAPI Loopback)
        if source in (AudioSourceType.SYSTEM, AudioSourceType.BOTH):
            try:
                wasapi_info = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
                def_output = self.pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                loopback = None

                for lb in self.pa.get_loopback_device_info_generator():
                    if def_output["name"] in lb["name"]:
                        loopback = lb
                        break

                if loopback is None:
                    for lb in self.pa.get_loopback_device_info_generator():
                        loopback = lb
                        break

                if loopback is not None:
                    ch = int(loopback["maxInputChannels"])
                    sr = int(loopback["defaultSampleRate"])
                    cb = self._make_callback("interviewer", self.vad_interviewer, orig_sr=sr, channels=ch)
                    self.stream_system = self.pa.open(
                        format=pyaudio.paFloat32,
                        channels=ch,
                        rate=sr,
                        input=True,
                        input_device_index=loopback["index"],
                        stream_callback=cb,
                    )
                    self.stream_system.start_stream()
                    self.device_system_name = loopback["name"]
                    started_system = True
                    logger.info("Interviewer stream started (WASAPI loopback)", device=self.device_system_name)
            except Exception as err:
                logger.warning("Could not start Interviewer loopback stream", error=str(err))

        # 2. Setup Interviewee stream (Microphone)
        if source in (AudioSourceType.MICROPHONE, AudioSourceType.BOTH):
            try:
                def_mic = self.pa.get_default_input_device_info()
                if device_id is not None:
                    try:
                        def_mic = self.pa.get_device_info_by_index(device_id)
                    except Exception:
                        pass

                if def_mic is not None and def_mic.get("maxInputChannels", 0) > 0:
                    ch = min(int(def_mic["maxInputChannels"]), 2)
                    sr = int(def_mic["defaultSampleRate"])
                    cb = self._make_callback("interviewee", self.vad_interviewee, orig_sr=sr, channels=ch)
                    self.stream_mic = self.pa.open(
                        format=pyaudio.paFloat32,
                        channels=ch,
                        rate=sr,
                        input=True,
                        input_device_index=def_mic["index"],
                        stream_callback=cb,
                    )
                    self.stream_mic.start_stream()
                    self.device_mic_name = def_mic["name"]
                    started_mic = True
                    logger.info("Interviewee stream started (Microphone)", device=self.device_mic_name)
            except Exception as err:
                logger.warning("Could not start Interviewee microphone stream", error=str(err))

        if started_system or started_mic:
            await self._dispatch_event(
                "audio.started",
                {
                    "source": source.value,
                    "interviewer_device": self.device_system_name,
                    "interviewee_device": self.device_mic_name,
                },
            )
            return True
        else:
            self.is_capturing = False
            logger.error("Failed to start any audio capture stream")
            await self._dispatch_event(
                "audio.error",
                {"code": "DEVICE_NOT_FOUND", "message": "No active audio capture device available"},
            )
            return False

    async def stop(self) -> None:
        """Stop all active audio capture streams."""
        if not self.is_capturing and not self.pa:
            return

        self.is_capturing = False

        for stream in (self.stream_system, self.stream_mic):
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    logger.error("Error closing audio stream", error=str(e))

        self.stream_system = None
        self.stream_mic = None
        self.device_system_name = None
        self.device_mic_name = None

        if self.pa:
            try:
                self.pa.terminate()
            except Exception:
                pass
            self.pa = None

        self.vad_interviewer.reset()
        self.vad_interviewee.reset()
        self.speech_frames["interviewer"] = []
        self.speech_frames["interviewee"] = []

        logger.info("All audio capture streams stopped")
        await self._dispatch_event("audio.stopped", {"reason": "user_action"})
