"""Tests for telegram_media_dl.rate_limiter."""
import time

import pytest

from telegram_media_dl.rate_limiter import RateLimiter


class TestRateLimiterAllow:
    def test_first_request_allowed(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        allowed, reset_in = rl.is_allowed(user_id=1)
        assert allowed is True
        assert reset_in == 0

    def test_requests_within_limit_allowed(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            allowed, _ = rl.is_allowed(user_id=1)
            assert allowed is True

    def test_request_exceeding_limit_blocked(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            rl.is_allowed(user_id=1)
        allowed, reset_in = rl.is_allowed(user_id=1)
        assert allowed is False
        assert reset_in > 0

    def test_different_users_independent(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        # Exhaust user 1
        for _ in range(2):
            rl.is_allowed(user_id=1)
        blocked, _ = rl.is_allowed(user_id=1)
        assert blocked is False
        # User 2 should still be allowed
        allowed, _ = rl.is_allowed(user_id=2)
        assert allowed is True


class TestRateLimiterReset:
    def test_reset_clears_limit(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        for _ in range(2):
            rl.is_allowed(user_id=1)
        blocked, _ = rl.is_allowed(user_id=1)
        assert blocked is False

        rl.reset(user_id=1)
        allowed, _ = rl.is_allowed(user_id=1)
        assert allowed is True

    def test_reset_unknown_user_noop(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.reset(user_id=999)  # Should not raise


class TestRateLimiterUsage:
    def test_get_usage_increments(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.is_allowed(user_id=1)
        rl.is_allowed(user_id=1)
        used, remaining = rl.get_usage(user_id=1)
        assert used == 2
        assert remaining == 3

    def test_get_usage_after_reset(self):
        rl = RateLimiter(max_requests=5, window_seconds=60)
        rl.is_allowed(user_id=1)
        rl.reset(user_id=1)
        used, remaining = rl.get_usage(user_id=1)
        assert used == 0
        assert remaining == 5


class TestSlidingWindow:
    def test_window_expires(self):
        """Requests outside the window should not count."""
        rl = RateLimiter(max_requests=2, window_seconds=1)
        rl.is_allowed(user_id=1)
        rl.is_allowed(user_id=1)
        # Exhaust immediately
        blocked, _ = rl.is_allowed(user_id=1)
        assert blocked is False

        # Simulate window passing by manipulating the queue directly
        q = rl._requests[1]
        old_time = time.time() - 2  # 2 seconds ago (past the 1s window)
        while q:
            q.popleft()
        q.append(old_time)  # stale entry

        # Now a new request should be allowed
        allowed, _ = rl.is_allowed(user_id=1)
        assert allowed is True
