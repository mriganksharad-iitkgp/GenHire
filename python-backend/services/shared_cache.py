"""Optional shared, bounded JSON cache. Mongo remains authoritative.

Configured Redis outages bypass caching, never create process-local data caches.
The rate limiter owns the bounded TLS connection pool; caches share that client.
"""
import hashlib
import json
import logging
import os
import re
import time
import uuid

logger = logging.getLogger(__name__)
MISSING = object()
_RELEASE = "if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"


class SharedCache:
    max_bytes = 256 * 1024

    def __init__(self):
        self.retry_at = 0

    @staticmethod
    def key(bucket, parts):
        if not re.fullmatch(r'[a-z0-9-]{1,48}', bucket):
            raise ValueError('Invalid cache bucket')
        scope = [os.getenv('RATE_LIMIT_NAMESPACE', 'genhire'), os.getenv('FLASK_ENV', 'development'),
                 os.getenv('DATABASE_NAME', 'default')]
        digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        return f'genhire:cache:v1:{digest(scope)[:20]}:{bucket}:{digest(parts)}'

    def _client(self):
        if not os.getenv('REDIS_URL', '').strip() or time.monotonic() < self.retry_at:
            return None
        from middleware.rate_limiter import store
        return store._client()

    def _failed(self, error):
        # Never log URLs, keys, data or exception messages containing credentials.
        if time.monotonic() >= self.retry_at:
            logger.warning('Shared cache bypassed (%s)', type(error).__name__)
        self.retry_at = time.monotonic() + 3

    def _decode(self, raw):
        if raw is None or len(raw) > self.max_bytes:
            return MISSING
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError, TypeError):
            return MISSING

    def get_many(self, bucket, parts):
        try:
            client = self._client()
            if client is not None and parts:
                return [self._decode(raw) for raw in client.mget([self.key(bucket, part) for part in parts])]
        except Exception as error:
            self._failed(error)
        return [MISSING for _ in parts]

    def get(self, bucket, parts):
        return self.get_many(bucket, [parts])[0]

    def set(self, bucket, parts, value, ttl):
        if not 1 <= ttl <= 3600:
            raise ValueError('Cache TTL must be 1-3600 seconds')
        try:
            raw = json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
            if len(raw.encode()) > self.max_bytes:
                return False
            client = self._client()
            if client is not None:
                return bool(client.set(self.key(bucket, parts), raw, ex=ttl))
        except Exception as error:
            self._failed(error)
        return False

    def delete(self, bucket, parts):
        try:
            client = self._client()
            if client is not None:
                client.delete(self.key(bucket, parts))
        except Exception as error:
            self._failed(error)

    def remember(self, bucket, parts, load, ttl, negative_ttl=15):
        value = self.get(bucket, parts)
        if value is not MISSING:
            return value
        client, token, locked = None, uuid.uuid4().hex, False
        lease = self.key(bucket, parts) + ':loading'
        try:
            client = self._client()
            if client is not None:
                locked = bool(client.set(lease, token, nx=True, ex=120))
                if not locked:
                    # Another instance is loading. Return an unavailable value
                    # to billing displays instead of duplicating expensive reads.
                    return None
        except Exception as error:
            self._failed(error)
        try:
            value = load()
            self.set(bucket, parts, value, negative_ttl if value is None else ttl)
            return value
        finally:
            if locked:
                try:
                    client.eval(_RELEASE, 1, lease, token)
                except Exception as error:
                    self._failed(error)


cache = SharedCache()
