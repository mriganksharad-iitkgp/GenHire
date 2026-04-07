from typing import Dict, List, Optional
from dataclasses import dataclass, field
import threading
from contextvars import ContextVar, Token


@dataclass
class UsageEvent:
    source: str
    model: str
    session_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    audio_seconds: float = 0.0
    character_count: int = 0
    cost: float = 0.0


class CostTracker:
    _instance = None
    _lock = threading.Lock()
    _session_context: ContextVar[Optional[str]] = ContextVar(
        "cost_tracker_session", default=None
    )

    # Pricing (approximate/assumed)
    PRICING = {
        # LLM pricing per 1M tokens
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gpt-5.2": {"input": 5.00, "output": 15.00},
        "gpt-5-mini": {"input": 0.25, "output": 1.00},
        "gemini-1.5-flash-latest": {"input": 0.075, "output": 0.30},
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        # Google Cloud Speech-to-Text (per minute, assumed $0.024/min)
        "google-stt": {"price_per_minute": 0.024},
        # Google Cloud Text-to-Speech (per 1M characters, assumed $4.00 for standard, $16.00 for Neural2)
        "google-tts": {"price_per_1m_chars": 4.00},
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CostTracker, cls).__new__(cls)
                    cls._instance.reset()
        return cls._instance

    def reset(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_stt_seconds = 0.0
        self.total_tts_characters = 0
        self.total_cost = 0.0
        self.events: List[UsageEvent] = []
        self.active_sessions = set()

    def set_session_context(self, session_id: Optional[str]) -> Token:
        """Bind a session id to the current execution context."""
        return self._session_context.set(session_id)

    def clear_session_context(self, token: Token):
        """Restore previous execution context session binding."""
        self._session_context.reset(token)

    def start_session(self, session_id: str):
        """Register a session as active for usage tracking."""
        if not session_id:
            return
        with self._lock:
            self.active_sessions.add(session_id)

    def end_session(self, session_id: str, clear_events: bool = False) -> Dict:
        """Return session summary and optionally purge its events."""
        summary = self.get_summary(session_id=session_id)
        with self._lock:
            self.active_sessions.discard(session_id)
            if clear_events:
                self.events = [
                    event for event in self.events if event.session_id != session_id
                ]
        return summary

    def _resolve_session_id(self, session_id: Optional[str]) -> Optional[str]:
        return session_id if session_id is not None else self._session_context.get()

    def _calculate_llm_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        model_key = "gpt-4o"
        for key in self.PRICING:
            if key in model.lower() and not any(s in key for s in ["stt", "tts"]):
                model_key = key
                break

        rates = self.PRICING.get(model_key, self.PRICING["gpt-4o"])
        input_cost = (prompt_tokens / 1_000_000) * rates["input"]
        output_cost = (completion_tokens / 1_000_000) * rates["output"]
        return input_cost + output_cost

    def _calculate_stt_cost(self, seconds: float) -> float:
        rate = self.PRICING["google-stt"]["price_per_minute"]
        return (seconds / 60.0) * rate

    def _calculate_tts_cost(self, characters: int) -> float:
        rate = self.PRICING["google-tts"]["price_per_1m_chars"]
        return (characters / 1_000_000.0) * rate

    def add_usage(
        self,
        source: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        session_id: Optional[str] = None,
    ):
        cost = self._calculate_llm_cost(model, prompt_tokens, completion_tokens)
        resolved_session_id = self._resolve_session_id(session_id)

        event = UsageEvent(
            source=source,
            model=model,
            session_id=resolved_session_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

        with self._lock:
            self.events.append(event)
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_cost += cost

    def add_stt_usage(
        self,
        source: str,
        seconds: float,
        model: str = "google-stt",
        session_id: Optional[str] = None,
    ):
        cost = self._calculate_stt_cost(seconds)
        resolved_session_id = self._resolve_session_id(session_id)
        event = UsageEvent(
            source=source,
            model=model,
            session_id=resolved_session_id,
            audio_seconds=seconds,
            cost=cost,
        )
        with self._lock:
            self.events.append(event)
            self.total_stt_seconds += seconds
            self.total_cost += cost

    def add_tts_usage(
        self,
        source: str,
        characters: int,
        model: str = "google-tts",
        session_id: Optional[str] = None,
    ):
        cost = self._calculate_tts_cost(characters)
        resolved_session_id = self._resolve_session_id(session_id)
        event = UsageEvent(
            source=source,
            model=model,
            session_id=resolved_session_id,
            character_count=characters,
            cost=cost,
        )
        with self._lock:
            self.events.append(event)
            self.total_tts_characters += characters
            self.total_cost += cost

    def get_summary(self, session_id: Optional[str] = None) -> Dict:
        if session_id is None:
            return {
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
                "total_stt_seconds": round(self.total_stt_seconds, 2),
                "total_tts_characters": self.total_tts_characters,
                "total_cost": round(self.total_cost, 6),
                "event_count": len(self.events),
            }

        with self._lock:
            session_events = [
                event for event in self.events if event.session_id == session_id
            ]

        total_prompt_tokens = sum(event.prompt_tokens for event in session_events)
        total_completion_tokens = sum(
            event.completion_tokens for event in session_events
        )
        total_stt_seconds = sum(event.audio_seconds for event in session_events)
        total_tts_characters = sum(event.character_count for event in session_events)
        total_cost = sum(event.cost for event in session_events)

        return {
            "session_id": session_id,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "total_stt_seconds": round(total_stt_seconds, 2),
            "total_tts_characters": total_tts_characters,
            "total_cost": round(total_cost, 6),
            "event_count": len(session_events),
        }

    def get_session_cost(self, session_id: Optional[str] = None) -> float:
        if session_id is None:
            return self.total_cost
        return float(self.get_summary(session_id=session_id).get("total_cost", 0.0))
