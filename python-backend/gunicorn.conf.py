import os

bind = "0.0.0.0:" + os.getenv("PORT", "5000")

# Native vision/gRPC work can block cooperative workers. simple-websocket
# supplies WebSocket support for this bounded thread pool.
worker_class = "gthread"
threads = 32

workers = 1  # Interview and Socket.IO state are process-local.

worker_connections = 1000
# A silent worker is recycled; request/provider deadlines are bounded separately.
timeout = 60

# Keepalive for persistent connections
keepalive = 65

# Error logging
errorlog = "-"
loglevel = "info"
accesslog = "-"
