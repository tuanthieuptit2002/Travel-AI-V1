"""Redis client, cache, and rate limiting."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_redis_client = None
_redis_lock = threading.Lock()
_memory_cache: Dict[str, Tuple[float, str]] = {}
_memory_rate: Dict[str, list[float]] = {}
_memory_lock = threading.Lock()


def get_redis(settings: Optional[Settings] = None):
    """Return a Redis client or None when unavailable."""
    global _redis_client
    cfg = settings or get_settings()
    with _redis_lock:
        if _redis_client is False:
            return None
        if _redis_client is not None:
            return _redis_client
        try:
            import redis

            client = redis.Redis.from_url(
                cfg.redis_url, decode_responses=True, socket_timeout=1.5
            )
            client.ping()
            _redis_client = client
            return _redis_client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable; using in-process fallback: %s", type(exc).__name__)
            _redis_client = False  # sentinel: tried and failed
            return None


def reset_redis_client() -> None:
    global _redis_client
    with _redis_lock:
        _redis_client = None


def clear_local_caches() -> None:
    """Clear in-process cache/rate-limit state (tests + failover mode)."""
    with _memory_lock:
        _memory_cache.clear()
        _memory_rate.clear()


def redis_ping(settings: Optional[Settings] = None) -> bool:
    client = get_redis(settings)
    if not client:
        return False
    try:
        return bool(client.ping())
    except Exception:  # noqa: BLE001
        return False


def cache_get(key: str) -> Optional[Any]:
    client = get_redis()
    if client:
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            return None
    with _memory_lock:
        item = _memory_cache.get(key)
        if not item:
            return None
        expires_at, raw = item
        if expires_at < time.time():
            _memory_cache.pop(key, None)
            return None
        return json.loads(raw)


def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    payload = json.dumps(value, default=str)
    client = get_redis()
    if client:
        try:
            client.setex(key, ttl_seconds, payload)
            return
        except Exception:  # noqa: BLE001
            pass
    with _memory_lock:
        _memory_cache[key] = (time.time() + ttl_seconds, payload)


def cache_key(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"tripmind:cache:{digest}"


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


def check_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int,
    settings: Optional[Settings] = None,
) -> None:
    cfg = settings or get_settings()
    if not cfg.rate_limit_enabled:
        return
    client = get_redis(cfg)
    now = time.time()
    if client:
        try:
            pipe = client.pipeline()
            redis_key = f"tripmind:rl:{key}"
            pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds + 1)
            _, _, count, _ = pipe.execute()
            if int(count) > limit:
                raise RateLimitExceeded(retry_after=window_seconds)
            return
        except RateLimitExceeded:
            raise
        except Exception:  # noqa: BLE001
            pass

    with _memory_lock:
        bucket = _memory_rate.setdefault(key, [])
        cutoff = now - window_seconds
        bucket[:] = [ts for ts in bucket if ts >= cutoff]
        if len(bucket) >= limit:
            raise RateLimitExceeded(retry_after=window_seconds)
        bucket.append(now)
