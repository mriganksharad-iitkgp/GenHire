"""
Shared Flask extension instances.

socketio is created here (unbound) so any module — app.py or the
controllers — can `from extensions import socketio` and either call
`.init_app(app)` once (app.py) or `.emit(...)` (controllers) without
creating a circular import back into app.py.
"""
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*")
