import multiprocessing

# Bind to 0.0.0.0:5000
bind = "0.0.0.0:5000"

# Use eventlet worker class for Flask-SocketIO compatibility
worker_class = "eventlet"

# Calculate optimal workers (usually 2-4 x $(NUM_CORES) + 1)
# For async workers like eventlet, 1 worker per core is often sufficient, 
# but we'll use a conservative number.
workers = 1 # We use 1 worker for eventlet with SocketIO to avoid sticky session issues without Redis, unless we setup a message queue.

# Eventlet allows thousands of concurrent connections per worker
worker_connections = 1000

# Keepalive for persistent connections
keepalive = 65

# Error logging
errorlog = "-"
loglevel = "info"
accesslog = "-"
