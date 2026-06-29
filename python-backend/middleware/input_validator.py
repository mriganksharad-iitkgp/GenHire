import re

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def validate_email(email: str):
    """Return error string or None if valid."""
    if not email or not isinstance(email, str):
        return 'Email is required'
    if len(email) > 254:
        return 'Email must be 254 characters or fewer'
    if not _EMAIL_RE.match(email.strip()):
        return 'Invalid email format'
    return None


def validate_password(password: str, field_name: str = 'Password'):
    """Return error string or None if valid."""
    if not password or not isinstance(password, str):
        return f'{field_name} is required'
    if len(password) < 8:
        return f'{field_name} must be at least 8 characters'
    if len(password) > 128:
        return f'{field_name} must be 128 characters or fewer'
    return None


def validate_name(name: str):
    """Return error string or None if valid."""
    if not name or not isinstance(name, str):
        return 'Name is required'
    stripped = name.strip()
    if not stripped:
        return 'Name is required'
    if len(stripped) > 100:
        return 'Name must be 100 characters or fewer'
    return None
