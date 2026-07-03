"""
Lightweight, dependency-cheap pre-classification for candidate answers.

Runs BEFORE any LLM evaluation call, so obviously-junk answers (empty,
canned "I don't know" phrases, gibberish, confidently-non-English text)
get a fast, deterministic, correctly-low score instead of being scored
purely on length (the old fallback behavior) or sent to an LLM at all.

Off-topic-but-fluent answers are deliberately NOT handled here — judging
topical relevance needs real language understanding, which only the LLM
evaluators can do (see the hardened prompts in answer_evaluator.py /
communication_evaluator.py).
"""

from typing import Optional, Tuple, TypedDict

try:
    from langdetect import detect, DetectorFactory, LangDetectException

    # Make detection deterministic — langdetect's default is seeded from
    # system time, which makes borderline strings flip between runs.
    DetectorFactory.seed = 0
    _LANGDETECT_AVAILABLE = True
except Exception:  # pragma: no cover - defensive: missing dependency shouldn't crash evaluation
    _LANGDETECT_AVAILABLE = False


_NON_ANSWER_PHRASES = [
    "i don't know",
    "i dont know",
    "idk",
    "not sure",
    "no idea",
    "i have no idea",
    "can't answer",
    "cant answer",
    "cannot answer",
    "skip this",
    "skip",
    "pass",
    "n/a",
    "not applicable",
    "no comment",
    "i don't know sorry",
]

# Non-answer detection is length-gated: a hedge like "I'm not entirely sure,
# but I believe X uses..." is a real attempted answer and must not match.
_NON_ANSWER_MAX_LENGTH = 40

# Gibberish heuristic is only meaningful with enough letters to measure a
# ratio from.
_GIBBERISH_MIN_LETTERS = 8
_VOWELS = set("aeiou")

# langdetect is unreliable on short strings (it can call "no" Norwegian) —
# only trust it once there's enough text.
_LANGDETECT_MIN_LENGTH = 30


class AnswerClassification(TypedDict):
    is_empty: bool
    is_non_answer: bool
    is_gibberish: bool
    is_non_english: bool
    detected_language: Optional[str]


def _looks_like_non_answer(normalized: str) -> bool:
    if len(normalized) > _NON_ANSWER_MAX_LENGTH:
        return False
    return any(phrase in normalized for phrase in _NON_ANSWER_PHRASES)


def _looks_like_gibberish(text: str) -> bool:
    letters = [c for c in text.lower() if c.isalpha()]
    if len(letters) < _GIBBERISH_MIN_LETTERS:
        return False

    vowel_ratio = sum(1 for c in letters if c in _VOWELS) / len(letters)
    # Real English text: vowel ratio is almost always ~30-50%. Outside a wider
    # 15-65% band is a strong signal of keyboard-mash or random characters.
    if vowel_ratio < 0.15 or vowel_ratio > 0.65:
        return True

    # A run of 6+ consecutive consonants essentially never occurs in real
    # English words/sentences.
    longest_run = 0
    current_run = 0
    for c in letters:
        if c in _VOWELS:
            current_run = 0
        else:
            current_run += 1
            longest_run = max(longest_run, current_run)
    return longest_run >= 6


def _detect_language(text: str) -> Optional[str]:
    if not _LANGDETECT_AVAILABLE or len(text.strip()) < _LANGDETECT_MIN_LENGTH:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None
    except Exception:
        return None


def classify_answer(answer: Optional[str]) -> AnswerClassification:
    """Classify a raw candidate answer before it reaches any LLM evaluator."""
    raw = answer or ""
    stripped = raw.strip()
    normalized = " ".join(stripped.lower().split())

    if not stripped:
        return {
            "is_empty": True,
            "is_non_answer": False,
            "is_gibberish": False,
            "is_non_english": False,
            "detected_language": None,
        }

    is_non_answer = _looks_like_non_answer(normalized)
    is_gibberish = _looks_like_gibberish(stripped)

    detected_language = None
    is_non_english = False
    # Skip language detection entirely once something else has already
    # explained why this isn't a scorable answer — no need to layer flags.
    if not is_non_answer and not is_gibberish:
        detected_language = _detect_language(stripped)
        is_non_english = detected_language is not None and detected_language != "en"

    return {
        "is_empty": False,
        "is_non_answer": is_non_answer,
        "is_gibberish": is_gibberish,
        "is_non_english": is_non_english,
        "detected_language": detected_language,
    }


def is_junk(classification: AnswerClassification) -> bool:
    """True if the answer should skip LLM scoring entirely."""
    return (
        classification["is_empty"]
        or classification["is_non_answer"]
        or classification["is_gibberish"]
        or classification["is_non_english"]
    )


def non_answer_score_and_reason(classification: AnswerClassification) -> Tuple[float, str]:
    """
    Deterministic (score 0-1, reasoning) for a junk-classified answer.

    Priority order matters: empty is the most certain signal, followed by
    gibberish, then a recognized non-answer phrase, then non-English (kept
    least severe since language-detection false positives on short technical
    answers are a real risk — flag it for the recruiter rather than zero it).
    """
    if classification["is_empty"]:
        return 0.0, "No answer was provided."
    if classification["is_gibberish"]:
        return 0.0, "The answer does not appear to be coherent text and could not be evaluated."
    if classification["is_non_answer"]:
        return (
            0.05,
            "Candidate indicated they did not know the answer — treated as unanswered for scoring purposes.",
        )
    if classification["is_non_english"]:
        lang = classification["detected_language"] or "a different language"
        return (
            0.15,
            f"Answer appears to be in {lang} rather than English; flagged for manual review.",
        )
    # Should not be reached if is_junk() gated the caller correctly.
    return 0.5, "Unable to classify answer confidently."
