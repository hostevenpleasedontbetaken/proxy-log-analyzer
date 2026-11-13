"""A small in-memory sliding-window rate limiter.

Uploads are the expensive request (parsing and detection use seconds of CPU), so they are
limited per person and overall. The counts live in each server process's memory: they reset
when a container restarts and are not shared between processes. That is enough here, because
the deployment runs a single small instance, and it avoids a database table or a paid service.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float, now: float | None = None) -> bool:
        """Record a hit and return True, unless `key` already has `limit` hits in the window."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


uploads_limiter = RateLimiter()
UPLOADS_PER_USER_PER_HOUR = 6
UPLOADS_PER_HOUR_OVERALL = 40
