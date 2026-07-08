"""Shared response helpers for controllers using schemas."""


def err(message, status):
    """The project's standard error tuple: ({'error': msg}, status)."""
    return {'error': message}, status
