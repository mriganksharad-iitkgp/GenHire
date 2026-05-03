"""
Centralized pricing configuration.

- LLM prices are in USD per token.
- GCP STT is billed per 15 seconds.
- GCP TTS is billed per character.
"""

PRICING = {
    "gpt-4.1": {
        "input": 0.00001,
        "output": 0.00003,
    },
    "gpt-4o-mini": {
        "input": 0.00000015,
        "output": 0.0000006,
    },
    "gcp_stt": {
        "default": 0.006,  # USD per 15 seconds
    },
    "gcp_tts": {
        "standard": 0.000004,  # USD per character
        "neural": 0.000016,  # USD per character
    },
}
