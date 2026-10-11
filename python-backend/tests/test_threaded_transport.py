"""Real local WebSocket heartbeat while a native request is blocked; no accounts."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import time
import unittest

from flask import Flask
import requests
import socketio as socketio_client
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.extensions import socketio
from core.development_server import DevelopmentRequestHandler


class ThreadedTransportTests(unittest.TestCase):
    def test_native_work_does_not_block_websocket_heartbeats_or_other_requests(self):
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test-only-secret"
        started, release = threading.Event(), threading.Event()
        @app.get("/native-work")
        def native_work():
            started.set(); release.wait(2)
            return {"ok": True}
        @socketio.on("test-heartbeat")
        def heartbeat(data):
            return {"ok": True}
        socketio.init_app(app, ping_interval=0.15, ping_timeout=0.3)
        self.assertEqual(socketio.async_mode, "threading")
        server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=DevelopmentRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        client = socketio_client.Client(reconnection=False)
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            client.connect(base, transports=["websocket"], wait_timeout=2)
            self.assertEqual(client.transport(), "websocket")
            with ThreadPoolExecutor(max_workers=1) as pool:
                blocked = pool.submit(requests.get, base + "/native-work", timeout=3)
                self.assertTrue(started.wait(1))
                try:
                    # Longer than the configured ping timeout. If native work
                    # starves heartbeats the socket disconnects here.
                    time.sleep(0.6)
                    self.assertTrue(client.connected)
                    self.assertEqual(client.call("test-heartbeat", {}, timeout=1), {"ok": True})
                finally:
                    release.set()
                self.assertEqual(blocked.result().status_code, 200)
        finally:
            release.set(); client.disconnect(); server.shutdown(); server.server_close(); thread.join(2)


if __name__ == "__main__":
    unittest.main()
