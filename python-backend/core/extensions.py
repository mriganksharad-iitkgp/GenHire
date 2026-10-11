"""
Shared Flask extension instances.

socketio is created here (unbound) so any module — the app factory or the
controllers — can `from core.extensions import socketio` and either call
`.init_app(app)` once (factory) or `.emit(...)` (controllers) without
creating a circular import back into the composition root.

The legacy import path `from extensions import socketio` keeps working via
the re-export shim at python-backend/extensions.py.
"""
from flask_socketio import SocketIO

# Native OpenCV and Google gRPC calls must not block an eventlet green-thread
# hub. Match Gunicorn's single-process gthread deployment explicitly, even
# when eventlet remains installed for legacy tooling.
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
