import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

TOO_MANY_ATTEMPTS = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many attempts. Please try again later.",
)


class InMemoryRateLimiter:
    """Fixed-window request limiter keyed by client IP.

    In-memory and per-process: resets on restart and is not shared across
    multiple worker processes. Sufficient for a single-instance deployment;
    swap for a shared store (e.g. Redis) if the app ever runs multiple workers.
    """

    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self._window_seconds

        timestamps = self._attempts[key]
        while timestamps and timestamps[0] < window_start:
            timestamps.pop(0)

        if len(timestamps) >= self._max_attempts:
            raise TOO_MANY_ATTEMPTS

        timestamps.append(now)


login_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60)
