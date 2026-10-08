"""
Thread-safe circular audio buffer for streaming audio frames to downstream STT.
"""

import collections
import threading
from typing import List, Optional
from app.audio.types import AudioChunk


class AudioBuffer:
    """Circular ring buffer for AudioChunk objects."""

    def __init__(self, max_chunks: int = 100):
        self._buffer: collections.deque = collections.deque(maxlen=max_chunks)
        self._lock = threading.Lock()

    def push(self, chunk: AudioChunk) -> None:
        """Add a chunk to the buffer."""
        with self._lock:
            self._buffer.append(chunk)

    def get_recent(self, count: int = 10) -> List[AudioChunk]:
        """Get the latest N chunks."""
        with self._lock:
            return list(self._buffer)[-count:]

    def clear(self) -> None:
        """Clear buffer contents."""
        with self._lock:
            self._buffer.clear()

    def get_concatenated_pcm(self, count: Optional[int] = None) -> bytes:
        """Concatenate PCM bytes of the most recent chunks."""
        with self._lock:
            chunks = list(self._buffer) if count is None else list(self._buffer)[-count:]
            return b"".join(c.data for c in chunks)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
