import os
import time
import threading
from collections import defaultdict, deque
from functools import wraps
from flask import request, jsonify

_lock = threading.Lock()
# key: "<endpoint_name>:<ip>" -> deque of monotonic timestamps
_windows: dict = defaultdict(deque)

_redis_client = None
_redis_init_attempted = False


def _get_redis_client():
    """
    Lazily create a Redis client the first time it's needed, only if
    REDIS_URL is configured. Returns None (callers fall back to the in-memory
    window) if unset or if the connection can't be established — so setting
    REDIS_URL is the only step needed to make rate limiting shared across
    multiple workers/containers; leaving it unset keeps today's behavior.
    """
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
        client.ping()
        _redis_client = client
    except Exception as e:
        print(f"[WARN] REDIS_URL is set but Redis connection failed ({e}); rate limiting falls back to in-memory.")
        _redis_client = None
    return _redis_client


def rate_limit(max_calls: int, window_seconds: int):
    """
    Per-IP rate limiter, shared across processes via Redis when REDIS_URL is
    configured and reachable; otherwise an in-process sliding window (correct
    for a single worker, but each additional worker/container tracks its own
    independent counters).
    Returns 429 with Retry-After header when the limit is exceeded.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or 'unknown').split(',')[0].strip()
            key = f'{f.__name__}:{ip}'

            redis_client = _get_redis_client()
            if redis_client is not None:
                try:
                    # Fixed-window counter: INCR then set an expiry only on
                    # the first hit in the window. Less precise than a true
                    # sliding window but standard, cheap, and correct enough
                    # for abuse prevention.
                    redis_key = f"rate_limit:{key}"
                    count = redis_client.incr(redis_key)
                    if count == 1:
                        redis_client.expire(redis_key, window_seconds)
                    if count > max_calls:
                        ttl = redis_client.ttl(redis_key)
                        retry_after = ttl if ttl and ttl > 0 else window_seconds
                        resp = jsonify({'error': 'Too many requests. Please try again later.'})
                        resp.status_code = 429
                        resp.headers['Retry-After'] = str(retry_after)
                        return resp
                    return f(*args, **kwargs)
                except Exception as e:
                    print(f"[WARN] Redis rate-limit check failed ({e}); falling back to in-memory for this request.")
                    # Fall through to the in-memory path below.

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
