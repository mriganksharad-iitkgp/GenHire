"""Socket.IO event handlers.

Importing the handler modules runs their @socketio.on decorators against the
shared socketio instance from extensions.py; call register_all() once from the
app composition root after the database is connected.
"""


def register_all():
    from sockets import proctoring_sockets, mobile_sockets  # noqa: F401
