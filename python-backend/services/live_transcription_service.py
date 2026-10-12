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

SAMPLE_RATE = 16000
WINDOW_BYTES = SAMPLE_RATE * 2 * 3
OVERLAP_BYTES = SAMPLE_RATE * 2 // 3
MAX_SECONDS = 185
SLOTS = threading.BoundedSemaphore(8)


def append_transcript(previous, additional):
    left, right = previous.split(), additional.split()
    normalize = lambda word: re.sub(r"[^\w]", "", word).casefold()
    overlap = 0
    for size in range(2, min(12, len(left), len(right)) + 1):
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
                    if self.samples > SAMPLE_RATE * MAX_SECONDS:
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

    def _recognize(self, pcm):
        if not has_speech_energy(pcm):
            return
        if not self.still_active():
            self.cancelled.set()
            return
        text = self.recognize(pcm)
        if text is None:
            raise RuntimeError("Caption recognition unavailable")
        if not self.cancelled.is_set() and str(text).strip():
            self.text = append_transcript(self.text, str(text).strip())
            self.emit({"stream_id": self.stream_id, "session_id": self.session_id,
                       "transcript": self.text, "final": False})

    def _run(self):
        buffer = bytearray()
        try:
            while not self.cancelled.is_set() and time.monotonic() - self.created < MAX_SECONDS + 10:
                try:
                    chunk = self.queue.get(timeout=10)
                except queue.Empty:
                    self.complete = False
                    break
                if chunk is None:
                    if len(buffer) > OVERLAP_BYTES:
                        self._recognize(bytes(buffer))
                    break
                buffer.extend(chunk)
                while len(buffer) >= WINDOW_BYTES:
                    self._recognize(bytes(buffer[:WINDOW_BYTES]))
                    del buffer[:WINDOW_BYTES - OVERLAP_BYTES]
            if self.cancelled.is_set():
                self.complete = False
        except Exception:
            self.complete = False
            self.emit({"stream_id": self.stream_id, "session_id": self.session_id,
                       "error": "Live captions are temporarily unavailable. Your recorded answer is still being saved."})
        finally:
            self.done.set()
            SLOTS.release()
