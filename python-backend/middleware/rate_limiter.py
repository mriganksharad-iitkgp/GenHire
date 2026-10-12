"""Atomic shared quotas and bounded admission; handlers never execute inside store catches."""
import hashlib
import logging
import math
import os
import threading
import time
from functools import wraps
from flask import g, jsonify, request
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)
COUNTER_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


def env_int(name, default, minimum=1, maximum=1000000):
    value = int(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return value


def shared_store_required():
    default = 'true' if os.getenv('FLASK_ENV', 'development') == 'production' else 'false'
    return os.getenv('RATE_LIMIT_REQUIRE_REDIS', default).lower() in ('1', 'true', 'yes')


class StoreUnavailable(Exception):
    pass


class CounterStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.windows = {}
        self.redis = None
        self.redis_url = None
        self.retry_at = 0
        self.last_sweep = 0

    def _client(self):
        url = os.getenv('REDIS_URL', '').strip()
        if not url:
            if shared_store_required():
                raise StoreUnavailable()
            return None
        if time.monotonic() < self.retry_at:
            raise StoreUnavailable()
        if self.redis is None or self.redis_url != url:
            import redis
            # Remote TLS setup can take several seconds. Bound connection and
            # command waits separately instead of failing healthy Redis at 500ms.
            connect_timeout = env_int('REDIS_CONNECT_TIMEOUT_MS', 5000, 100, 30000) / 1000
            socket_timeout = env_int('REDIS_SOCKET_TIMEOUT_MS', 2000, 100, 30000) / 1000
            # Fail promptly on an outage; redis-py's automatic retries multiply
            # these waits and stall protected requests.
            from redis.backoff import NoBackoff
            from redis.retry import Retry
            self.redis = redis.Redis.from_url(
                url, socket_timeout=socket_timeout,
                socket_connect_timeout=connect_timeout, health_check_interval=30,
                retry=Retry(NoBackoff(), 0))
            self.redis_url = url
        return self.redis

    def hit(self, key, window):
        try:
            client = self._client()
            if client is not None:
                count, ttl = client.eval(COUNTER_SCRIPT, 1, key, window)
                return int(count), max(1, int(ttl))
        except Exception as exc:
            # Exception text and URLs can contain passwords; log only the type.
            self.retry_at = time.monotonic() + 3
            logger.warning('Request protection store unavailable (%s)', type(exc).__name__)
            raise StoreUnavailable() from None
        now = time.monotonic()
        with self.lock:
            if now - self.last_sweep > 30:
                self.windows = {k: v for k, v in self.windows.items() if v[1] > now}
                self.last_sweep = now
            entry = self.windows.get(key)
            if entry is None or entry[1] <= now:
                if entry is None and len(self.windows) >= env_int('RATE_LIMIT_MEMORY_KEYS', 20000):
                    raise StoreUnavailable()
                entry = [0, now + window]
                self.windows[key] = entry
            entry[0] += 1
            return entry[0], max(1, math.ceil(entry[1] - now))


store = CounterStore()


def rejection(status, code, retry_after, policy):
    message = (f'Too many requests. Please try again in {retry_after} seconds.'
               if status == 429 else 'The service is busy. Please try again shortly.')
    response = jsonify(error=message, error_code=code, retry_after=retry_after, policy=policy)
    response.status_code = status
    response.headers['Retry-After'] = str(retry_after)
    response.headers['Cache-Control'] = 'no-store'
    return response


def check_limit(policy, identity, limit, window):
    digest = hashlib.sha256(str(identity).encode()).hexdigest()
    namespace = os.getenv('RATE_LIMIT_NAMESPACE', 'genhire')
    try:
        count, retry = store.hit(f'{namespace}:quota:{policy}:{digest}', window)
    except StoreUnavailable:
        return rejection(503, 'protection_unavailable', 3, policy)
    if count > limit:
        return rejection(429, 'rate_limited', retry, policy)
    return None


POLICIES = {
    'auth': (120, 60), 'account': (600, 60), 'login': (10, 60), 'register': (5, 300),
    'email': (3, 300), 'invite_redeem': (20, 300),
    'application': (5, 60), 'application_hour': (30, 3600),
    'ai': (10, 300), 'upload': (12, 300), 'invite_send': (5, 300),
    'interview_start': (4, 300), 'interview_answer': (60, 60),
    'interview_setup': (60, 60), 'telemetry': (600, 60),
    'speech': (120, 60), 'speech_token': (20, 60), 'payment': (20, 300),
    'socket_connect': (120, 60), 'socket_control': (120, 60),
    'socket_frame': (180, 60), 'socket_status': (60, 60),
    'socket_audio': (720, 60),
    'export': (10, 300), 'read': (240, 60), 'write': (60, 60),
}


def route_policy(endpoint, method, path=''):
    name = (endpoint or '').split('.')[-1]
    if name == 'google_oauth':
        return 'auth'
    if name in ('login', 'check_email_account_type', 'reset_password', 'verify_email'):
        return 'login'
    if name == 'register':
        return 'register'
    if name in ('forgot_password', 'resend_verification'):
        return 'email'
    if name in ('lookup_invite_route', 'redeem_invite_route'):
        return 'invite_redeem'
    if name == 'apply_for_job':
        return 'application'
    if name in ('generate_jd_with_ai', 'check_cv_match_score', 'recalculate_cv_score', 'chat_with_cost_tracking'):
        return 'ai'
    if name in ('start_interview', 'start_practice_interview'):
        return 'interview_start'
    if name in ('submit_answer', 'submit_practice_answer', 'get_interview_question'):
        return 'interview_answer'
    if name in ('register_face', 'activate_interview', 'end_interview', 'end_practice_interview'):
        return 'interview_setup'
    if name == 'upload_gaze_recorder_results':
        return 'telemetry'
    if name == 'speech_token':
        return 'speech_token'
    if name in ('transcribe', 'synthesize', 'stt_cost', 'tts_cost'):
        return 'speech'
    if name in ('preview_invites', 'send_invites'):
        return 'invite_send'
    if 'export' in name:
        return 'export'
    if method in ('POST', 'PUT', 'PATCH') and ('upload' in name or 'identity-card' in path):
        return 'upload'
    if '/payment' in path and method != 'GET':
        return 'payment'
    return 'read' if method in ('GET', 'HEAD') else 'write'


def signed_identity():
    """Only signature-verified user IDs get account buckets; routes still enforce auth."""
    import jwt
    from core.security import get_jwt_secret
    token = request.headers.get('Authorization') or request.args.get('token', '')
    if token.startswith('Bearer '):
        token = token[7:]
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=['HS256'])
        user_id = payload.get('user_id')
        if isinstance(user_id, str) and len(user_id) == 24:
            return 'user:' + user_id
    except (jwt.InvalidTokenError, ValueError, TypeError):
        pass
    return None


def policy_budget(policy):
    limit, window = POLICIES[policy]
    prefix = 'RATE_LIMIT_' + policy.upper()
    return env_int(prefix + '_CALLS', limit), env_int(prefix + '_WINDOW_SECONDS', window)


def install_request_protection(app):
    from werkzeug.middleware.proxy_fix import ProxyFix
    hops = env_int('TRUSTED_PROXY_HOPS', 0, minimum=0, maximum=10)
    if hops:
        # Direct ingress must be blocked when trusting forwarded headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops)
    for policy in POLICIES:
        policy_budget(policy)
    if shared_store_required():
        try:
            store._client().ping()
        except Exception as exc:
            # Include the failure class for Cloud Run diagnostics, never its text
            # (which can contain the Redis URL/password).
            raise RuntimeError(
                'Request protection requires reachable REDIS_URL in production '
                f'({type(exc).__name__}); check TLS, secret access and Redis timeouts'
            ) from None
    lock = threading.Lock()
    active = {}
    capacities = {
        'requests': env_int('API_MAX_INFLIGHT', 128),
        'ai': env_int('AI_MAX_INFLIGHT', 6), 'upload': env_int('UPLOAD_MAX_INFLIGHT', 8),
        'speech': env_int('SPEECH_MAX_INFLIGHT', 12),
        'interview_start': env_int('INTERVIEW_START_MAX_INFLIGHT', 6),
        'invite_send': env_int('INVITE_MAX_INFLIGHT', 2),
    }
    app.extensions['request_protection'] = {'active': active, 'capacities': capacities}

    @app.before_request
    def protect_request():
        if request.method == 'OPTIONS' or request.path in ('/', '/health'):
            return None
        # Bound body parsing/JWT checks as well as the business handler.
        with lock:
            if active.get('requests', 0) >= capacities['requests']:
                return rejection(503, 'capacity_busy', 2, 'requests')
            active['requests'] = active.get('requests', 0) + 1
            g.admitted_groups = ['requests']
        webhook = request.path.startswith('/api/payment/') and request.path.endswith('/webhooks/razorpay')
        ip = request.remote_addr or 'unknown'
        g.rate_limit_identity = signed_identity()
        blocked = check_limit('network', ip, env_int('RATE_LIMIT_NETWORK_CALLS', 3000), 60)
        if blocked:
            return blocked
        policy = route_policy(request.endpoint, request.method, request.path)
        if not webhook:
            identity = g.rate_limit_identity or 'ip:' + ip
            if g.rate_limit_identity:
                blocked = check_limit('account', identity, *policy_budget('account'))
                if blocked:
                    return blocked
            if policy in ('auth', 'login', 'register', 'email'):
                data = request.get_json(silent=True)
                if data is not None and not isinstance(data, dict):
                    return jsonify(error='Request data must be a JSON object.'), 400
                data = data or {}
                target = str(data.get('identifier') or data.get('email') or '').strip().lower()[:320]
                blocked = check_limit('auth_network', ip, *policy_budget('auth'))
                if blocked:
                    return blocked
                if policy != 'auth':
                    identity = 'target:' + target if target else identity
            blocked = check_limit(policy, identity, *policy_budget(policy))
            if blocked:
                return blocked
            if policy == 'application':
                blocked = check_limit('application_hour', identity, *policy_budget('application_hour'))
                if blocked:
                    return blocked
        groups = [policy] if policy in capacities else []
        with lock:
            if any(active.get(group, 0) >= capacities[group] for group in groups):
                return rejection(503, 'capacity_busy', 2, policy)
            for group in groups:
                active[group] = active.get(group, 0) + 1
            g.admitted_groups.extend(groups)

    @app.teardown_request
    def release_capacity(_error):
        groups = g.pop('admitted_groups', [])
        with lock:
            for group in groups:
                active[group] -= 1


def rate_limit(max_calls, window_seconds, key_func=None):
    """Compatibility for isolated views; installed applications use central policies."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import current_app
            if 'request_protection' not in current_app.extensions and request.method != 'OPTIONS':
                identity = key_func(*args, **kwargs) if key_func else None
                identity = identity or g.get('rate_limit_identity') or request.remote_addr or 'unknown'
                blocked = check_limit(f.__name__, identity, max_calls, window_seconds)
                if blocked:
                    return blocked
            return f(*args, **kwargs)
        return wrapper
    return decorator



_frame_slots = None
_frame_lock = threading.Lock()


def socket_limit(policy):
    """Bound socket abuse before database/model calls; return native acknowledgements."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from sockets.session_access import socket_contexts
            context = socket_contexts.get(request.sid) or {}
            identity = ('user:' + context['user_id'] if context.get('user_id')
                        else 'ip:' + (request.remote_addr or 'unknown'))
            blocked = check_limit(policy, identity, *policy_budget(policy))
            if blocked:
                if policy == 'socket_connect':
                    return False
                return {'ok': False, 'accepted': False,
                        'error_code': 'rate_limited' if blocked.status_code == 429 else 'protection_unavailable',
                        'retry_after': int(blocked.headers['Retry-After'])}
            acquired = False
            if policy == 'socket_frame':
                global _frame_slots
                with _frame_lock:
                    if _frame_slots is None:
                        _frame_slots = threading.BoundedSemaphore(env_int('PROCTORING_MAX_INFLIGHT', 4))
                acquired = _frame_slots.acquire(blocking=False)
                if not acquired:
                    return {'ok': True, 'accepted': False, 'reason': 'busy'}
            try:
                return f(*args, **kwargs)
            except ConnectionFailure:
                if policy == "socket_connect":
                    from sockets.session_access import contexts_lock
                    with contexts_lock:
                        socket_contexts.pop(request.sid, None)
                    return False
                return {"ok": False, "accepted": False, "error_code": "database_busy", "retry_after": 3}
            finally:
                if acquired:
                    _frame_slots.release()
        return wrapper
    return decorator
