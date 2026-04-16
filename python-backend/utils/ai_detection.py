import os
import requests
import json
import logging

logger = logging.getLogger(__name__)

def check_ai_content(text_to_check: str):
    """
    Checks if the given text is AI-generated using Sapling AI's detection API.
    Returns a dictionary with 'score' (0.0 to 1.0, where 1.0 is high probability of AI),
    or None if the check failed or wasn't configured.
    """
    if not text_to_check or len(text_to_check.strip()) < 20:
        return None # text too short for meaningful analysis

    api_key = os.environ.get("SAPLING_API_KEY")
    if not api_key:
        logger.warning("SAPLING_API_KEY environment variable is not set. Skipping AI detection.")
        return None

    url = "https://api.sapling.ai/api/v1/aidetect"
    
    payload = {
        "key": api_key,
        "text": text_to_check
    }
    
    try:
        # 10s timeout to ensure we don't unduly block the interview flow
        response = requests.post(url, json=payload, timeout=10)
        
        if 200 <= response.status_code < 300:
            result = response.json()
            overall_score = result.get("score", 0)
            return {
                "score": overall_score,
                "raw_response": result
            }
        else:
            logger.error(f"Sapling API Error {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Sapling API hit timeout limit.")
        return None
    except Exception as e:
        logger.error(f"Sapling API connection error: {e}")
        return None
