import time
import threading
from collections import defaultdict, deque
from functools import wraps
from flask import request, jsonify

_lock = threading.Lock()
# key: "<endpoint_name>:<ip>" -> deque of monotonic timestamps
_windows: dict = defaultdict(deque)


def rate_limit(max_calls: int, window_seconds: int):
    """
    Per-IP sliding-window rate limiter.
    Works independently of Flask-Limiter — no shared state required.
    Returns 429 with Retry-After header when the limit is exceeded.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or 'unknown').split(',')[0].strip()
            key = f'{f.__name__}:{ip}'
            now = time.monotonic()
            cutoff = now - window_seconds
            with _lock:
                dq = _windows[key]
                while dq and dq[0] < cutoff:
                    dq.popleft()
                if len(dq) >= max_calls:
                    retry_after = int(window_seconds - (now - dq[0])) + 1
                    resp = jsonify({'error': 'Too many requests. Please try again later.'})
                    resp.status_code = 429
                    resp.headers['Retry-After'] = str(retry_after)
                    return resp
                dq.append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator
