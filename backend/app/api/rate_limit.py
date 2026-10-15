"""In-process token-bucket rate limiting for expensive endpoints (Plan §16.6, roadmap R2-P3 task 5).

Applied as a dependency, e.g. ``dependencies=[Depends(rate_limited("recommend"))]`` on
``/recommend`` and ``/whatif/sensitivity``. Limit: ``SMQI_RATE_LIMIT_PER_MIN`` requests per minute
per client and bucket. Single-process prototype: no Redis (Plan §20).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from app.api.errors import ApiError, ErrorCode


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    def __init__(self, per_minute: int, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.capacity = float(per_minute)
        self.rate = per_minute / 60.0
        self._clock = clock
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, client: str, bucket: str) -> tuple[bool, float]:
        """Consume one token; return (allowed, seconds until the next token)."""
        now = self._clock()
        with self._lock:
            b = self._buckets.get((client, bucket))
            if b is None:
                b = self._buckets[(client, bucket)] = _Bucket(self.capacity, now)
            b.tokens = min(self.capacity, b.tokens + (now - b.updated) * self.rate)
            b.updated = now
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True, 0.0
            return False, (1.0 - b.tokens) / self.rate


def rate_limited(bucket: str) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        limiter: TokenBucketLimiter = request.app.state.rate_limiter
        client = request.client.host if request.client else "unknown"
        allowed, retry_after = limiter.allow(client, bucket)
        if not allowed:
            raise ApiError(
                ErrorCode.RATE_LIMITED,
                f"Too many '{bucket}' requests; retry in {retry_after:.1f} s",
                hint="Expensive endpoints are rate limited per client.",
            )

    return dependency
