from typing import Dict, List, Optional
from dataclasses import dataclass, field
import threading


@dataclass
class UsageEvent:
    source: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    audio_seconds: float = 0.0
    character_count: int = 0
    cost: float = 0.0


class CostTracker:
    _instance = None
    _lock = threading.Lock()

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
        self.session_totals: Dict[str, Dict] = {}

    def start_session(self, session_id: str):
        with self._lock:
            self.session_totals[str(session_id)] = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_stt_seconds": 0.0,
                "total_tts_characters": 0,
                "total_cost": 0.0,
                "event_count": 0,
            }

    def _merge_session_totals(
        self,
        session_id: Optional[str],
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        stt_seconds: float = 0.0,
        tts_characters: int = 0,
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

        event = UsageEvent(
            source=source,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

        with self._lock:
            self.events.append(event)
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_cost += cost
            self._merge_session_totals(
                session_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
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
        event = UsageEvent(source=source, model=model, audio_seconds=seconds, cost=cost)
        with self._lock:
            self.events.append(event)
            self.total_stt_seconds += seconds
            self.total_cost += cost
            self._merge_session_totals(
                session_id,
                stt_seconds=seconds,
                cost=cost,
            )

    def add_tts_usage(
        self,
        source: str,
        characters: int,
        model: str = "google-tts",
        session_id: Optional[str] = None,
    ):
        cost = self._calculate_tts_cost(characters)
        event = UsageEvent(
            source=source, model=model, character_count=characters, cost=cost
        )
        with self._lock:
            self.events.append(event)
            self.total_tts_characters += characters
            self.total_cost += cost
            self._merge_session_totals(
                session_id,
                tts_characters=characters,
                cost=cost,
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

    def get_summary(self) -> Dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_stt_seconds": round(self.total_stt_seconds, 2),
            "total_tts_characters": self.total_tts_characters,
            "total_cost": round(self.total_cost, 6),
            "event_count": len(self.events),
        }

    def get_session_cost(self) -> float:
        return self.total_cost
