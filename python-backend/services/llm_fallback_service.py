"""
LLM Fallback Service — the app-wide resilient LLM chain with automatic
failover on quota exhaustion.

Provider ORDER comes from the environment (primary -> secondary -> tertiary):
    LLM_PROVIDER_PRIORITY=deepseek,gemini,groq      (single-var form)
or  LLM_PRIMARY_PROVIDER / LLM_SECONDARY_PROVIDER / LLM_TERTIARY_PROVIDER

Default order: deepseek, gemini, groq (S2 Low).
"gemini" and "google" are aliases.
Per-provider models: LLM_DEEPSEEK_MODEL, LLM_GEMINI_MODEL, LLM_GROQ_MODEL.
LLM_OPENAI_MODEL is retained only for explicitly configured legacy chains.

Detects quota/rate-limit errors and transparently switches to the next
available provider. Tracks exhausted providers with a cooldown so we
don't keep hammering a provider that already told us "no".
"""

import os
import time
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, replace
from threading import Lock

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error classification helpers
# ---------------------------------------------------------------------------

# Patterns that indicate quota / rate-limit exhaustion
_QUOTA_ERROR_PATTERNS = [
    r"429",
    r"rate.?limit",
    r"quota",
    r"resource.?exhausted",
    r"too.?many.?requests",
    r"capacity",
    r"billing",
    r"exceeded",
    r"insufficient_quota",
    r"tokens.?per.?min",
    r"requests.?per.?min",
    r"RPM",
    r"TPM",
]

_QUOTA_RE = re.compile("|".join(_QUOTA_ERROR_PATTERNS), re.IGNORECASE)


def is_quota_error(error: Exception) -> bool:
    """Return True if *error* looks like a quota/rate-limit problem."""
    error_str = str(error)
    # Check the error message text
    if _QUOTA_RE.search(error_str):
        return True
    # Some SDKs expose a status_code attribute
    status = getattr(error, "status_code", None) or getattr(
        error, "http_status", None
    )
    if status == 429:
        return True
    # google-api-core wraps gRPC codes
    code = getattr(error, "code", None)
    if code is not None:
        code_val = getattr(code, "value", code)
        if code_val == 8 or code_val == 429:  # RESOURCE_EXHAUSTED
            return True
    return False


# ---------------------------------------------------------------------------
# Provider priority (primary / secondary / tertiary) — shared app-wide
# ---------------------------------------------------------------------------

_ALIASES = {"gemini": "google", "google": "google", "openai": "openai", "groq": "groq", "deepseek": "deepseek"}
_DEFAULT_PRIORITY = ["deepseek", "google", "groq"]

PROVIDER_SPECS = {
    "deepseek": {"key_env": "DEEPSEEK_API_KEY", "model_env": "LLM_DEEPSEEK_MODEL",
                 "default_model": "deepseek-flash"},
    "google": {"key_env": "GOOGLE_API_KEY", "model_env": "LLM_GEMINI_MODEL",
               "default_model": "gemini-3.1-flash-lite"},
    "openai": {"key_env": "OPENAI_API_KEY", "model_env": "LLM_OPENAI_MODEL",
               "default_model": "gpt-4o-mini"},
    "groq":   {"key_env": "GROQ_API_KEY", "model_env": "LLM_GROQ_MODEL",
               "default_model": "openai/gpt-oss-20b"},
}


def get_provider_priority() -> List[str]:
    """Canonical provider order from the environment (primary first).

    LLM_PROVIDER_PRIORITY="groq,gemini,openai" wins; otherwise the
    LLM_PRIMARY/SECONDARY/TERTIARY_PROVIDER triple; otherwise the default.
    Unknown names are ignored; an explicit list limits which providers run.
    """
    raw = os.getenv("LLM_PROVIDER_PRIORITY", "").strip()
    if raw:
        names = [part.strip().lower() for part in raw.split(",")]
    else:
        names = [
            (os.getenv("LLM_PRIMARY_PROVIDER") or "").strip().lower(),
            (os.getenv("LLM_SECONDARY_PROVIDER") or "").strip().lower(),
            (os.getenv("LLM_TERTIARY_PROVIDER") or "").strip().lower(),
        ]

    ordered = []
    for name in names:
        canonical = _ALIASES.get(name)
        if canonical and canonical not in ordered:
            ordered.append(canonical)
    # An explicitly configured chain is authoritative. In particular, never
    # append OpenAI just because an old key remains in the environment.
    return ordered or list(_DEFAULT_PRIORITY)


def default_model_for(provider: str) -> str:
    """Provider's default model: LLM_<P>_MODEL env, else the built-in.
    Legacy CV envs (CV_SCORING_MODEL / OPENAI_CV_MODEL / GROQ_CV_MODEL) are
    still honored so existing deployments keep their explicit choices."""
    spec = PROVIDER_SPECS[provider]
    legacy = {
        "google": os.getenv("CV_SCORING_MODEL"),
        "openai": os.getenv("OPENAI_CV_MODEL"),
        "groq": os.getenv("GROQ_CV_MODEL"),
    }.get(provider)
    return os.getenv(spec["model_env"]) or legacy or spec["default_model"]


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    provider_type: str  # 'google', 'openai', 'groq'
    api_key: str
    model: str
    temperature: float = 0.3
    max_retries: int = 2          # retries *within* this provider
    retry_base_delay: float = 1.0  # seconds
    cooldown_seconds: float = 300  # 5 min cooldown after quota error
    timeout_seconds: float = 30
    max_tokens: Optional[int] = None


@dataclass
class _CooldownEntry:
    exhausted_at: float = 0.0
    cooldown_seconds: float = 300


class LLMFallbackService:
    """
    Invoke an LLM prompt with automatic provider failover.

    Usage::

        service = LLMFallbackService()
        result = service.invoke(prompt_text)
        # result = {
        #     'content': '...',
        #     'provider_used': 'google',
        #     'model_used': 'gemini-flash-latest',
        #     'fallback_triggered': False,
        #     'usage': { ... },
        # }
    """

    def __init__(self, providers: Optional[List[ProviderConfig]] = None):
        self._providers = providers or self._build_default_providers()
        self._cooldowns: Dict[str, _CooldownEntry] = {}
        self._lock = Lock()

        if not self._providers:
            raise ValueError(
                "No LLM providers configured. Ensure at least one of "
                "DEEPSEEK_API_KEY, GOOGLE_API_KEY, or GROQ_API_KEY is set."
            )

        names = [p.name for p in self._providers]
        logger.info(f"LLMFallbackService initialised with providers: {names}")

    # ------------------------------------------------------------------
    # Default provider chain from .env
    # ------------------------------------------------------------------

    @staticmethod
    def _build_default_providers() -> List[ProviderConfig]:
        providers = []
        for name in get_provider_priority():
            spec = PROVIDER_SPECS[name]
            api_key = os.getenv(spec["key_env"], "").strip()
            if not api_key:
                continue
            providers.append(ProviderConfig(
                name=name,
                provider_type=name,
                api_key=api_key,
                model=default_model_for(name),
                temperature=0.3,
            ))
        return providers

    # ------------------------------------------------------------------
    # Cooldown tracking
    # ------------------------------------------------------------------

    def _is_on_cooldown(self, provider_name: str) -> bool:
        with self._lock:
            entry = self._cooldowns.get(provider_name)
            if entry is None:
                return False
            elapsed = time.time() - entry.exhausted_at
            if elapsed >= entry.cooldown_seconds:
                # Cooldown expired — provider eligible again
                del self._cooldowns[provider_name]
                logger.info(f"Provider '{provider_name}' cooldown expired, re-enabling")
                return False
            return True

    def _mark_exhausted(self, provider_name: str, cooldown_seconds: float):
        with self._lock:
            self._cooldowns[provider_name] = _CooldownEntry(
                exhausted_at=time.time(),
                cooldown_seconds=cooldown_seconds,
            )
        logger.warning(
            f"Provider '{provider_name}' marked exhausted, "
            f"cooldown={cooldown_seconds}s"
        )

    # ------------------------------------------------------------------
    # LLM instantiation per provider type
    # ------------------------------------------------------------------

    @staticmethod
    def _create_llm(config: ProviderConfig):
        """Instantiate the appropriate LangChain chat model."""
        if config.provider_type == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=config.model,
                temperature=config.temperature,
                google_api_key=config.api_key,
                max_retries=0,
                timeout=config.timeout_seconds,
                max_output_tokens=config.max_tokens,
            )
        elif config.provider_type in ("openai", "deepseek"):
            from langchain_openai import ChatOpenAI
            provider_options = {}
            if config.provider_type == "deepseek":
                provider_options = {
                    "base_url": os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
                    "extra_body": {"thinking": {"type": os.getenv("DEEPSEEK_THINKING_MODE", "disabled")}},
                }
            return ChatOpenAI(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_retries=0,
                timeout=config.timeout_seconds,
                max_tokens=config.max_tokens,
                **provider_options,
            )
        elif config.provider_type == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_retries=0,
                timeout=config.timeout_seconds,
                max_tokens=config.max_tokens,
            )
        else:
            raise ValueError(f"Unknown provider type: {config.provider_type}")

    # ------------------------------------------------------------------
    # Core invocation with fallback
    # ------------------------------------------------------------------

    def invoke(
        self,
        prompt: str,
        json_mode: bool = False,
        images: Optional[List[Tuple[bytes, str]]] = None,
        model_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke the prompt against the provider chain.

        Args:
            prompt: The input prompt text.
            json_mode: If True, forces JSON output via model kwargs and cleans up markdown.
            images: Optional list of (bytes, content_type) attached as vision
                inputs (callers must pass vision-capable model_overrides).
            model_overrides: Optional {provider_name: model} map for
                task-specific models (e.g. vision models for face matching).

        Returns a dict with keys:
            content       – str, the LLM response text
            provider_used – str, name of the provider that succeeded
            model_used    – str, model that produced the response
            fallback_triggered – bool, True if primary provider failed
            usage         – dict or None, token usage metadata
            raw_response  – the original LangChain response object
        """
        errors: List[Tuple[str, Exception]] = []
        primary_name = self._providers[0].name if self._providers else None

        payload = self._build_payload(prompt, images)

        for base_cfg in self._providers:
            # GPT-OSS 20B is text-only. Vision tasks stop after Gemini unless
            # the caller explicitly supplies a different Groq vision model.
            if images and base_cfg.provider_type == "groq" and not (model_overrides or {}).get("groq"):
                continue
            provider_cfg = base_cfg
            override = (model_overrides or {}).get(base_cfg.name)
            if override and override != base_cfg.model:
                provider_cfg = replace(base_cfg, model=override)

            if self._is_on_cooldown(provider_cfg.name):
                logger.info(f"Skipping provider '{provider_cfg.name}' (on cooldown)")
                continue

            for attempt in range(1, provider_cfg.max_retries + 1):
                try:
                    llm = self._create_llm(provider_cfg)
                    
                    if json_mode:
                        if provider_cfg.provider_type in ["openai", "deepseek", "groq"]:
                            llm = llm.bind(response_format={"type": "json_object"})

                    response = llm.invoke(payload)

                    content = response.content
                    if not isinstance(content, str):
                        content = str(content)

                    if json_mode:
                        # Clean up markdown codeblocks if they exist
                        content = content.strip()
                        if content.startswith("```json"):
                            content = content[7:]
                        if content.startswith("```"):
                            content = content[3:]
                        if content.endswith("```"):
                            content = content[:-3]
                        content = content.strip()

                    # Extract usage metadata
                    usage = self._extract_usage(response)
                    from services.provider_usage_service import record_provider_request
                    record_provider_request(provider_cfg.provider_type, provider_cfg.model, usage)

                    return {
                        "content": content,
                        "provider_used": provider_cfg.name,
                        "model_used": provider_cfg.model,
                        "fallback_triggered": provider_cfg.name != primary_name,
                        "usage": usage,
                        "raw_response": response,
                    }

                except Exception as e:
                    errors.append((provider_cfg.name, e))

                    if is_quota_error(e):
                        logger.warning(
                            f"Quota/rate-limit error on '{provider_cfg.name}' "
                            f"(attempt {attempt}/{provider_cfg.max_retries}): {e}"
                        )
                        # If we still have retries for this provider, wait & retry
                        if attempt < provider_cfg.max_retries:
                            delay = provider_cfg.retry_base_delay * (2 ** (attempt - 1))
                            logger.info(f"Retrying '{provider_cfg.name}' in {delay}s...")
                            time.sleep(delay)
                            continue
                        else:
                            # All retries for this provider exhausted — cooldown & try next
                            self._mark_exhausted(
                                provider_cfg.name, provider_cfg.cooldown_seconds
                            )
                            break
                    else:
                        # Non-quota error — log and try next provider immediately
                        logger.error(
                            f"Non-quota error on '{provider_cfg.name}' "
                            f"(attempt {attempt}): {e}"
                        )
                        if attempt < provider_cfg.max_retries:
                            delay = provider_cfg.retry_base_delay * (2 ** (attempt - 1))
                            time.sleep(delay)
                            continue
                        else:
                            break

        # All providers exhausted
        error_summary = "; ".join(
            f"{name}: {str(err)[:200]}" for name, err in errors
        )
        raise LLMAllProvidersExhaustedError(
            f"All LLM providers failed. Errors: {error_summary}",
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Message building (text or multimodal)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(prompt: str, images: Optional[List[Tuple[bytes, str]]]):
        """Plain string for text prompts; LangChain multimodal message when
        images are attached (image_url data URLs work across OpenAI/Groq/
        Gemini chat models)."""
        if not images:
            return prompt

        import base64
        from langchain_core.messages import HumanMessage

        content = [{"type": "text", "text": prompt}]
        for image_bytes, content_type in images:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{content_type or 'image/jpeg'};base64,{encoded}"},
            })
        return [HumanMessage(content=content)]

    # ------------------------------------------------------------------
    # Usage extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_usage(response) -> Optional[Dict[str, Any]]:
        from services.usage_telemetry_service import extract_usage_from_response
        return extract_usage_from_response(response)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMQuotaExhaustedError(Exception):
    """Raised when a single provider's quota is exhausted."""
    pass


class LLMAllProvidersExhaustedError(Exception):
    """Raised when ALL providers in the fallback chain have failed."""

    def __init__(self, message: str, errors: Optional[List[Tuple[str, Exception]]] = None):
        super().__init__(message)
        self.errors = errors or []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_fallback_service: Optional[LLMFallbackService] = None


def get_llm_fallback_service() -> LLMFallbackService:
    """Get or create the global LLMFallbackService singleton."""
    global _fallback_service
    if _fallback_service is None:
        _fallback_service = LLMFallbackService()
    return _fallback_service
