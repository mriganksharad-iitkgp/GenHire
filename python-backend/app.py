"""GenHire backend entrypoint.

The composition root lives in core/factory.py (create_app); this module stays
as the stable target for both deployment commands:

    gunicorn ... app:app          (Cloud Run / start_server.sh)
    python app.py                 (local dev server with reloader)
"""

import core.bootstrap  # noqa: F401  side effects: UTF-8 stdout, TF/glog silencing

from core.extensions import socketio
from core.factory import create_app

app = create_app()

if __name__ == "__main__":
    from jobs import runner as jobs_runner

    try:
        # socketio.run instead of app.run to enable the WebSocket eventlet server
        socketio.run(app, debug=True, host="0.0.0.0", port=5000, use_reloader=True)
    finally:
        jobs_runner.stop_all()
