"""Per-user rate limiting for telegram-media-dl."""
import time
import logging
from collections import defaultdict, deque
from typing import Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter per user ID."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        # user_id -> deque of timestamps
        self._requests: dict = defaultdict(deque)

    def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user is within rate limit.
        Returns (allowed, seconds_until_reset).
        """
        now = time.time()
        window_start = now - self.window
        q = self._requests[user_id]

        # Evict old timestamps
        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= self.max_requests:
            reset_in = int(q[0] + self.window - now) + 1
            logger.debug("Rate limit hit for user %d, reset in %ds", user_id, reset_in)
            return False, reset_in

        q.append(now)
        return True, 0

    def reset(self, user_id: int) -> None:
        """Manually reset rate limit for a user (admin use)."""
        self._requests.pop(user_id, None)

    def get_usage(self, user_id: int) -> Tuple[int, int]:
        """Return (used, remaining) for this window."""
        now = time.time()
        window_start = now - self.window
        q = self._requests[user_id]
        while q and q[0] < window_start:
            q.popleft()
        used = len(q)
        return used, max(0, self.max_requests - used)

    def get_all_usage(self) -> dict:
        """Return usage stats for all users."""
        now = time.time()
        window_start = now - self.window
        result = {}
        for uid, q in self._requests.items():
            while q and q[0] < window_start:
                q.popleft()
            if q:
                result[uid] = len(q)
        return result
