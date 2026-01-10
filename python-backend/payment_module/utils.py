"""
Payment Module Utilities

Helper functions for the payment module.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def generate_idempotency_key(prefix: str = "pay") -> str:
    """
    Generate a unique idempotency key.

    Args:
        prefix: Key prefix for identification

    Returns:
        Unique idempotency key string
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:12]
    return f"{prefix}_{timestamp}_{unique_id}"


def cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars"""
    return cents / 100


def dollars_to_cents(dollars: float) -> int:
    """Convert dollars to cents"""
    return int(dollars * 100)


def format_currency(cents: int, currency: str = "USD") -> str:
    """
    Format cents as currency string.

    Args:
        cents: Amount in cents
        currency: Currency code

    Returns:
        Formatted string (e.g., "$49.00")
    """
    dollars = cents / 100

    currency_symbols = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}

    symbol = currency_symbols.get(currency.upper(), "$")
    return f"{symbol}{dollars:.2f}"


def is_valid_object_id(id_string: str) -> bool:
    """
    Check if string is a valid MongoDB ObjectId.

    Args:
        id_string: String to validate

    Returns:
        Boolean indicating validity
    """
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        ObjectId(id_string)
        return True
    except (InvalidId, TypeError):
        return False


def safe_get_nested(data: dict, *keys, default=None):
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to traverse
        *keys: Keys to follow
        default: Default value if not found

    Returns:
        Found value or default
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
        if result is None:
            return default
    return result
