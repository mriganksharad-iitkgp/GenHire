"""Legacy import path — the shared socketio instance moved to core/extensions.py.

Kept as a permanent re-export so the many controllers doing
`from extensions import socketio` keep working unchanged.
"""
from core.extensions import socketio  # noqa: F401
