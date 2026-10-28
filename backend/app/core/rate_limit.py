"""Thread-safe, sliding-window in-memory rate limiter for sensitive endpoints."""

from __future__ import annotations

import collections
import threading
import time
from typing import Callable

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding-window counter rate limiter."""

    def __init__(self) -> None:
        self._history: dict[str, collections.deque[float]] = collections.defaultdict(
            collections.deque
        )
        self._lock = threading.Lock()

    def check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        """Record an attempt and raise HTTP 429 if the request limit is exceeded."""
        if max_requests <= 0:
            return

        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._history[key]
            # Prune timestamps older than window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= max_requests:
                earliest = timestamps[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)

    def reset(self) -> None:
        """Clear all rate limit history (used in testing)."""
        with self._lock:
            self._history.clear()


GLOBAL_RATE_LIMITER = RateLimiter()


def get_client_ip(request: Request) -> str:
    """Safely extract the client IP address from the request."""
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit(
    max_requests: int,
    window_seconds: int = 60,
    key_prefix: str = "global",
) -> Callable[[Request], None]:
    """Dependency that applies rate limiting based on client IP and optional endpoint prefix."""

    async def _dep(request: Request) -> None:
        client_ip = get_client_ip(request)
        key = f"{key_prefix}:{client_ip}"
        GLOBAL_RATE_LIMITER.check(key, max_requests=max_requests, window_seconds=window_seconds)

    return _dep
