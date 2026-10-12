"""Bounded incremental captions using the application's configured STT service.

Whisper accepts complete files, so PCM is transcribed in small overlapping WAV
windows. These are real recognition results; final answer transcription remains
the recorded-audio authority. No microphone samples or text are logged here.
"""
import array
import queue
import re
import threading
import time
import logging
import math

SAMPLE_RATE = 16000
# Four-second cadence (15 requests/minute), with eight seconds of context.
# Keep the newest four seconds revisable as the next window adds context.
STEP_BYTES = SAMPLE_RATE * 2 * 4
WINDOW_BYTES = STEP_BYTES * 2
OVERLAP_BYTES = STEP_BYTES
MAX_SECONDS = 185
SLOTS = threading.BoundedSemaphore(8)
logger = logging.getLogger(__name__)


def append_transcript(previous, additional):
    left, right = previous.split(), additional.split()
    normalize = lambda word: re.sub(r"[^\w]", "", word).casefold()
    overlap = 0
    for size in range(1, min(12, len(left), len(right)) + 1):
        if list(map(normalize, left[-size:])) == list(map(normalize, right[:size])):
            overlap = size
    return " ".join(left + right[overlap:]).strip()


def has_speech_energy(pcm):
    samples = array.array("h", pcm)
    if not samples:
        return False
    return sum(value * value for value in samples) / len(samples) > (32768 * .006) ** 2


class LiveTranscript:
    def __init__(self, stream_id, session_id, recognize, emit, still_active):
        self.stream_id, self.session_id = stream_id, session_id
        self.recognize, self.emit, self.still_active = recognize, emit, still_active
        self.queue = queue.Queue(maxsize=64)
        self.condition = threading.Condition()
        self.pending = {}
        self.sequence = 0
        self.samples = 0
        self.text = ""
        self.words = []
        self.complete = True
        self.closed = False
        self.done = threading.Event()
        self.cancelled = threading.Event()
        self.created = time.monotonic()

    def start(self):
        if not SLOTS.acquire(blocking=False):
            return False
        threading.Thread(target=self._run, daemon=True, name="live-interview-captions").start()
        return True

    def add(self, sequence, pcm):
        if not isinstance(pcm, (bytes, bytearray)) or not 0 < len(pcm) <= 12800 or len(pcm) % 2:
            return False
        with self.condition:
            if self.closed or self.done.is_set() or time.monotonic() - self.created > MAX_SECONDS or not isinstance(sequence, int) or isinstance(sequence, bool):
                return False
            if sequence < self.sequence:
                return True
            if sequence > self.sequence + 8:
                self.complete = False
                return False
            self.pending.setdefault(sequence, bytes(pcm))
            try:
                while self.sequence in self.pending:
                    chunk = self.pending.pop(self.sequence)
                    self.samples += len(chunk) // 2
                    # Audio is already owner-bound and bounded per stream. A
                    # local real-time budget avoids a Redis round trip per packet.
                    if self.samples > SAMPLE_RATE * min(MAX_SECONDS, time.monotonic() - self.created + 12):
                        self.complete = False
                        return False
                    self.queue.put_nowait(chunk)
                    self.sequence += 1
            except queue.Full:
                self.complete = False
                return False
            self.condition.notify_all()
        return True

    def finish(self, last_sequence, timeout=8):
        with self.condition:
            self.condition.wait_for(lambda: self.sequence > last_sequence or self.closed, timeout=.5)
            self.complete = self.complete and self.sequence == last_sequence + 1 and not self.pending
            self.closed = True
        try:
            self.queue.put(None, timeout=.5)
        except queue.Full:
            self.complete = False
            self.cancelled.set()
        finished = self.done.wait(timeout)
        return {"transcript": self.text, "complete": bool(finished and self.complete), "stream_id": self.stream_id}

    def cancel(self):
        self.cancelled.set()
        self.closed = True
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass

    def _recognize(self, pcm, offset=0):
        if not has_speech_energy(pcm):
            return
        if not self.still_active():
            self.cancelled.set()
            return
        # Only confirmed earlier context belongs in the hint; feeding the
        # overlapping draft back would reinforce its first recognition errors.
        earlier = " ".join(word["word"] for word in self.words if word["end"] <= offset)
        result = self.recognize(pcm, " ".join(earlier.split()[-60:]))
        if result is None:
            raise RuntimeError("Caption recognition unavailable")
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        if not self.cancelled.is_set() and str(text).strip():
            words = result.get("words") if isinstance(result, dict) else None
            if words:
                # Replace the overlapping draft, rather than appending another
                # recognition of the same sound. Keep only earlier stable words.
                stable = [word for word in self.words if word["end"] <= offset]
                boundary = stable[-1]["end"] if stable else offset
                revised = []
                duration = len(pcm) / (SAMPLE_RATE * 2)
                for word in words:
                    start, end = float(word.get("start", 0)), float(word.get("end", 0))
                    value = str(word.get("word", "")).strip()
                    if value and math.isfinite(start) and math.isfinite(end) and 0 <= start <= end <= duration + .25 and offset + end > boundary + .05:
                        revised.append({"word": value, "start": offset + start, "end": offset + end})
                if revised:
                    self.words = stable + revised
                    self.text = " ".join(word["word"] for word in self.words)
            else:
                self.text = append_transcript(self.text, str(text).strip())
            self.emit({"stream_id": self.stream_id, "session_id": self.session_id,
                       "transcript": self.text, "final": False, "provisional": True})

    def _run(self):
        buffer = bytearray()
        offset = 0
        fresh = 0
        try:
            while not self.cancelled.is_set() and time.monotonic() - self.created < MAX_SECONDS + 10:
                try:
                    chunk = self.queue.get(timeout=10)
                except queue.Empty:
                    self.complete = False
                    break
                if chunk is None:
                    if fresh:
                        self._recognize(bytes(buffer), offset)
                    break
                buffer.extend(chunk)
                fresh += len(chunk)
                if fresh >= STEP_BYTES:
                    self._recognize(bytes(buffer), offset)
                    fresh = 0
                    if len(buffer) >= WINDOW_BYTES:
                        removed = len(buffer) - OVERLAP_BYTES
                        del buffer[:removed]
                        offset += removed / (SAMPLE_RATE * 2)
            if self.cancelled.is_set():
                self.complete = False
        except Exception as exc:
            logger.warning("Live captions stopped (%s)", type(exc).__name__)
            self.complete = False
            self.emit({"stream_id": self.stream_id, "session_id": self.session_id,
                       "error_code": "caption_provider_unavailable",
                       "error": "Live captions are temporarily unavailable. Your recorded answer is still being saved."})
        finally:
            self.done.set()
            SLOTS.release()
