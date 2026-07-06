from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import threading
import math
from contextvars import ContextVar, Token
from .pricing import PRICING
from .speech_cost_tracker import (
    calculate_stt_cost,
    calculate_tts_cost_from_characters,
    log_cost,
)


def calculate_cost(model: str, usage: Any):
    """Return actual LLM cost in USD based only on provider usage payload."""
    if not usage or model not in PRICING:
        return None

    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
    else:
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)

    if prompt_tokens is None or completion_tokens is None:
        return None

    try:
        prompt_tokens = int(prompt_tokens)
        completion_tokens = int(completion_tokens)
    except (TypeError, ValueError):
        return None

    input_price = PRICING[model]["input"]
    output_price = PRICING[model]["output"]
    return (prompt_tokens * input_price) + (completion_tokens * output_price)



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
    calculated_cost: float = 0.0
    actual_cost: Optional[float] = None


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
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        # gemini-1.5-flash was retired by Google; gemini-2.5-flash is the
        # current fallback model (see session_manager._create_fallback_llm).
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        # Google Cloud Speech-to-Text (per minute, assumed $0.024/min)
        "google-stt": {"price_per_minute": 0.024},
        # Google Cloud Text-to-Speech (per 1M characters, assumed $4.00 for standard, $16.00 for Neural2)
        "google-tts": {"price_per_1m_chars": 4.00},
    }
    
    # Factor for safe margin estimates
    SAFETY_MARGIN = 1.1

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
        self.total_calculated_cost = 0.0
        self.total_actual_cost = 0.0
        self.total_cost = 0.0
        self.events: List[UsageEvent] = []
        self.active_sessions = set()
        self.session_totals: Dict[str, Dict] = {}

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
            self.session_totals[str(session_id)] = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_stt_seconds": 0.0,
                "total_tts_characters": 0,
                "total_calculated_cost": 0.0,
                "total_actual_cost": 0.0,
                "total_cost": 0.0,
                "event_count": 0,
            }

    def _resolve_session_id(self, session_id: Optional[str]) -> Optional[str]:
        return session_id if session_id is not None else self._session_context.get()

    def _merge_session_totals(
        self,
        session_id: Optional[str],
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        stt_seconds: float = 0.0,
        tts_characters: int = 0,
        calculated_cost: float = 0.0,
        actual_cost: Optional[float] = None,
        cost: float = 0.0,
    ):
        if not session_id:
            return

        session_key = str(session_id)
        current = self.session_totals.get(session_key)
        if current is None:
            self.start_session(session_key)
            current = self.session_totals.get(session_key)

        current["total_prompt_tokens"] += int(prompt_tokens or 0)
        current["total_completion_tokens"] += int(completion_tokens or 0)
        current["total_stt_seconds"] += float(stt_seconds or 0.0)
        current["total_tts_characters"] += int(tts_characters or 0)
        current["total_calculated_cost"] += float(calculated_cost or 0.0)
        if actual_cost is not None:
            current["total_actual_cost"] += float(actual_cost)
        current["total_cost"] += float(cost or 0.0)
        current["event_count"] += 1

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
        
        # Apply safety margin to the calculated cost
        return (input_cost + output_cost) * self.SAFETY_MARGIN

    def _calculate_stt_cost(self, seconds: float) -> float:
        cost = calculate_stt_cost(seconds)
        return float(cost or 0.0)

    def _calculate_tts_cost(self, characters: int, model: str = "google-tts") -> float:
        voice_type = "neural" if "neural" in str(model or "").lower() else "standard"
        cost = calculate_tts_cost_from_characters(characters, voice_type=voice_type)
        return float(cost or 0.0)

    def add_usage(
        self,
        source: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        session_id: Optional[str] = None,
        prompt_text: str = "",
        completion_text: str = "",
        usage: Any = None,
    ):
        raw_prompt_tokens = int(prompt_tokens or 0)
        raw_completion_tokens = int(completion_tokens or 0)

        actual_cost = calculate_cost(model, usage)

        # Fallback estimation if tokens are not provided (approx 4 chars per token)
        if prompt_tokens <= 0 and prompt_text:
            prompt_tokens = len(prompt_text) // 4
        if completion_tokens <= 0 and completion_text:
            completion_tokens = len(completion_text) // 4

        calculated_cost = self._calculate_llm_cost(model, prompt_tokens, completion_tokens)
        cost = calculated_cost
        resolved_session_id = self._resolve_session_id(session_id)

        event = UsageEvent(
            source=source,
            model=model,
            session_id=resolved_session_id,
            prompt_tokens=raw_prompt_tokens or int(prompt_tokens or 0),
            completion_tokens=raw_completion_tokens or int(completion_tokens or 0),
            cost=cost,
            calculated_cost=calculated_cost,
            actual_cost=actual_cost,
        )

        with self._lock:
            self.events.append(event)
            self.total_prompt_tokens += event.prompt_tokens
            self.total_completion_tokens += event.completion_tokens
            self.total_calculated_cost += calculated_cost
            if actual_cost is not None:
                self.total_actual_cost += actual_cost
            self.total_cost += cost
            self._merge_session_totals(
                resolved_session_id,
                prompt_tokens=event.prompt_tokens,
                completion_tokens=event.completion_tokens,
                calculated_cost=calculated_cost,
                actual_cost=actual_cost,
                cost=cost,
            )

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
            calculated_cost=cost,
        )
        with self._lock:
            self.events.append(event)
            self.total_stt_seconds += seconds
            self.total_calculated_cost += cost
            self.total_cost += cost
            self._merge_session_totals(
                session_id,
                stt_seconds=seconds,
                calculated_cost=cost,
                cost=cost,
            )
        try:
            stt_seconds_val = float(seconds)
        except (TypeError, ValueError):
            stt_seconds_val = 0.0
        log_cost(
            "gcp_stt",
            cost,
            {
                "source": source,
                "session_id": resolved_session_id,
                "audio_seconds": stt_seconds_val,
                "billed_seconds": (math.ceil(stt_seconds_val / 15.0) * 15)
                if stt_seconds_val > 0
                else 0,
            },
        )

    def add_tts_usage(
        self,
        source: str,
        characters: int,
        model: str = "google-tts",
        session_id: Optional[str] = None,
    ):
        cost = self._calculate_tts_cost(characters, model=model)
        resolved_session_id = self._resolve_session_id(session_id)
        event = UsageEvent(
            source=source,
            model=model,
            session_id=resolved_session_id,
            character_count=characters,
            cost=cost,
            calculated_cost=cost,
        )
        with self._lock:
            self.events.append(event)
            self.total_tts_characters += characters
            self.total_calculated_cost += cost
            self.total_cost += cost
            self._merge_session_totals(
                session_id,
                tts_characters=characters,
                calculated_cost=cost,
                cost=cost,
            )
        log_cost(
            "gcp_tts",
            cost,
            {
                "source": source,
                "session_id": resolved_session_id,
                "characters": int(characters or 0),
                "voice_type": "neural" if "neural" in str(model or "").lower() else "standard",
            },
        )

    def build_usage_summary(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        stt_seconds: float = 0.0,
        tts_characters: int = 0,
        llm_model: str = "llama-3.3-70b-versatile",
    ) -> Dict:
        llm_cost = self._calculate_llm_cost(
            llm_model,
            int(prompt_tokens or 0),
            int(completion_tokens or 0),
        )
        stt_cost = self._calculate_stt_cost(float(stt_seconds or 0.0))
        tts_cost = self._calculate_tts_cost(int(tts_characters or 0))

        total_cost = llm_cost + stt_cost + tts_cost
        return {
            "total_prompt_tokens": int(prompt_tokens or 0),
            "total_completion_tokens": int(completion_tokens or 0),
            "total_tokens": int(prompt_tokens or 0) + int(completion_tokens or 0),
            "total_stt_seconds": round(float(stt_seconds or 0.0), 2),
            "total_tts_characters": int(tts_characters or 0),
            "total_calculated_cost": round(total_cost, 6),
            "total_actual_cost": None,
            "total_cost": round(total_cost, 6),
            "event_count": 0,
        }

    def end_session(
        self,
        session_id: str,
        clear_events: bool = True,
        fallback: Optional[Dict] = None,
    ) -> Dict:
        """Return per-session usage summary; if unavailable, build from fallback totals."""
        session_key = str(session_id)

        with self._lock:
            session_data = self.session_totals.get(session_key)

            if session_data is not None:
                summary = {
                    "total_prompt_tokens": int(
                        session_data.get("total_prompt_tokens", 0) or 0
                    ),
                    "total_completion_tokens": int(
                        session_data.get("total_completion_tokens", 0) or 0
                    ),
                    "total_tokens": int(session_data.get("total_prompt_tokens", 0) or 0)
                    + int(session_data.get("total_completion_tokens", 0) or 0),
                    "total_stt_seconds": round(
                        float(session_data.get("total_stt_seconds", 0.0) or 0.0), 2
                    ),
                    "total_tts_characters": int(
                        session_data.get("total_tts_characters", 0) or 0
                    ),
                    "total_calculated_cost": round(
                        float(session_data.get("total_calculated_cost", 0.0) or 0.0), 6
                    ),
                    "total_actual_cost": round(
                        float(session_data.get("total_actual_cost", 0.0) or 0.0), 6
                    ),
                    "total_cost": round(
                        float(session_data.get("total_cost", 0.0) or 0.0), 6
                    ),
                    "event_count": int(session_data.get("event_count", 0) or 0),
                }
            else:
                fallback_data = fallback or {}
                summary = self.build_usage_summary(
                    prompt_tokens=int(fallback_data.get("total_prompt_tokens", 0) or 0),
                    completion_tokens=int(
                        fallback_data.get("total_completion_tokens", 0) or 0
                    ),
                    stt_seconds=float(
                        fallback_data.get("total_stt_seconds", 0.0) or 0.0
                    ),
                    tts_characters=int(
                        fallback_data.get("total_tts_characters", 0) or 0
                    ),
                    llm_model=fallback_data.get("model", "llama-3.3-70b-versatile"),
                )

            if clear_events and session_key in self.session_totals:
                del self.session_totals[session_key]

            return summary

    def get_summary(self, session_id: Optional[str] = None) -> Dict:
        if session_id is None:
            return {
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
                "total_stt_seconds": round(self.total_stt_seconds, 2),
                "total_tts_characters": self.total_tts_characters,
                "total_calculated_cost": round(self.total_calculated_cost, 6),
                "total_actual_cost": round(self.total_actual_cost, 6),
                "total_cost": round(self.total_cost, 6),
                "event_count": len(self.events),
            }

        with self._lock:
            session_data = self.session_totals.get(str(session_id))
            
            if session_data:
                prompt_tokens = int(session_data.get("total_prompt_tokens", 0))
                completion_tokens = int(session_data.get("total_completion_tokens", 0))
                stt_seconds = float(session_data.get("total_stt_seconds", 0.0))
                tts_characters = int(session_data.get("total_tts_characters", 0))
                calculated_cost = float(session_data.get("total_calculated_cost", 0.0))
                actual_cost = float(session_data.get("total_actual_cost", 0.0))
                cost = float(session_data.get("total_cost", 0.0))
                event_count = int(session_data.get("event_count", 0))
            else:
                # Fallback to scanning events if session_totals is missing for some reason
                session_events = [
                    event for event in self.events if event.session_id == session_id
                ]
                prompt_tokens = sum(event.prompt_tokens for event in session_events)
                completion_tokens = sum(event.completion_tokens for event in session_events)
                stt_seconds = sum(event.audio_seconds for event in session_events)
                tts_characters = sum(event.character_count for event in session_events)
                calculated_cost = sum(event.calculated_cost for event in session_events)
                actual_cost = sum(float(event.actual_cost or 0.0) for event in session_events)
                cost = sum(event.cost for event in session_events)
                event_count = len(session_events)

        return {
            "total_prompt_tokens": prompt_tokens,
            "total_completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "total_stt_seconds": round(stt_seconds, 2),
            "total_tts_characters": tts_characters,
            "total_calculated_cost": round(calculated_cost, 6),
            "total_actual_cost": round(actual_cost, 6),
            "total_cost": round(cost, 6),
            "event_count": event_count,
        }

    def get_session_cost(self, session_id: Optional[str] = None) -> float:
        if session_id is None:
            return self.total_cost
        return float(self.get_summary(session_id=session_id).get("total_cost", 0.0))
