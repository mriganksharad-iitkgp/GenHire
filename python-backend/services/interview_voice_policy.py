"""Public timing settings; shared by website and installed kiosk at session load."""
import math
import os


def bounded_number(name, default, minimum, maximum):
    try:
        value = float(os.getenv(name, default))
        return max(minimum, min(maximum, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def voice_policy():
    return {
        "silence_seconds": bounded_number("INTERVIEW_SILENCE_SECONDS", 5, 2, 30),
        "initial_wait_seconds": bounded_number("INTERVIEW_INITIAL_WAIT_SECONDS", 10, 5, 120),
        "max_answer_seconds": bounded_number("INTERVIEW_MAX_ANSWER_SECONDS", 180, 30, 180),
        "speech_level": bounded_number("INTERVIEW_SPEECH_LEVEL", 6, 2, 50),
        "speech_hold_ms": bounded_number("INTERVIEW_SPEECH_HOLD_MS", 240, 120, 1000),
    }
