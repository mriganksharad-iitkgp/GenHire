"""Werkzeug's local HTTP handler with clean WebSocket connection teardown."""
from werkzeug.serving import WSGIRequestHandler


class DevelopmentRequestHandler(WSGIRequestHandler):
    def connection_dropped(self, error, environ=None):
        # Engine.IO raises ConnectionError after a Werkzeug WebSocket closes.
        # End this HTTP handler too; unread close frames are not another HTTP
        # request and must not be logged as malformed requests.
        self.close_connection = True
        return super().connection_dropped(error, environ)
