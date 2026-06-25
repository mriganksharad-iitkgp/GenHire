"""
Common utility functions for the GenHire application
"""
import datetime
from typing import List, Union

def normalize_list_field(val: Union[str, List[str]], separator: str = ',') -> List[str]:
    """
    Normalize list-like fields that might be sent as strings
    Handles both comma and newline separated values
    """
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        # Try both newline and comma separated values
        text = val.replace('\r', '').strip()
        parts = []
        for chunk in text.split('\n'):
            parts.extend([p.strip() for p in chunk.split(separator)])
        return [p for p in parts if p]
    return []

def format_datetime_for_json(dt: datetime.datetime) -> str:
    """Format datetime object for JSON serialization"""
    if isinstance(dt, datetime.datetime):
        return dt.isoformat()
    return dt

def calculate_age_from_date(birth_date: datetime.datetime) -> int:
    """Calculate age from birth date"""
    today = datetime.date.today()
    birth_date = birth_date.date() if isinstance(birth_date, datetime.datetime) else birth_date
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length with ellipsis"""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def generate_slug(text: str) -> str:
    """Generate URL-friendly slug from text"""
    import re
    # Convert to lowercase and replace spaces with hyphens
    slug = text.lower().strip()
    # Remove special characters except hyphens
    slug = re.sub(r'[^a-z0-9\-]', '-', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug

def safe_int_conversion(value: Union[str, int], default: int = 0) -> int:
    """Safely convert value to integer with default fallback"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float_conversion(value: Union[str, float], default: float = 0.0) -> float:
    """Safely convert value to float with default fallback"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def extract_numeric_score(score_value) -> Union[float, None]:
    """Extract numeric score from various input types, excluding 'N/A'"""
    if isinstance(score_value, (int, float)):
        return float(score_value)
    elif isinstance(score_value, str):
        if score_value.replace('.', '', 1).isdigit():
            return float(score_value)
    return None
