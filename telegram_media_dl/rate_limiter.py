"""Per-user sliding-window rate limiter for telegram-media-dl."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter keyed by user ID."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: Dict[int, deque] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """
        Check whether *user_id* may make another request.

        Returns ``(allowed, seconds_until_reset)``.
        ``seconds_until_reset`` is 0 when allowed.
        """
        now = time.time()
        window_start = now - self.window
        q = self._requests[user_id]

        # Evict timestamps outside the current window
        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= self.max_requests:
            reset_in = int(q[0] + self.window - now) + 1
            logger.debug(
                "Rate limit hit for user %d; reset in %ds", user_id, reset_in
            )
            return False, reset_in

        q.append(now)
        return True, 0

    def reset(self, user_id: int) -> None:
        """Manually clear the rate-limit counter for *user_id*."""
        self._requests.pop(user_id, None)

    def get_usage(self, user_id: int) -> Tuple[int, int]:
        """Return ``(used, remaining)`` within the current window."""
        now = time.time()
        window_start = now - self.window
        q = self._requests[user_id]
        while q and q[0] < window_start:
            q.popleft()
        used = len(q)
        return used, max(0, self.max_requests - used)

    def get_all_usage(self) -> Dict[int, int]:
        """Return a snapshot of current usage counts for all users."""
        now = time.time()
        window_start = now - self.window
        result: Dict[int, int] = {}
        for uid, q in self._requests.items():
            while q and q[0] < window_start:
                q.popleft()
            if q:
                result[uid] = len(q)
        return result
