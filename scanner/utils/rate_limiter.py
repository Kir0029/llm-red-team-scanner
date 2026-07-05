"""Rate limiter utility for LLM Red Team Scanner."""

import asyncio
import time
from collections import deque


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Usage:
        limiter = RateLimiter(max_requests=60, window_seconds=60)
        await limiter.acquire()
        # Make API call...
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = time.monotonic()

            # Remove timestamps outside the window
            while self._timestamps and self._timestamps[0] <= now - self.window_seconds:
                self._timestamps.popleft()

            # If at capacity, wait until oldest timestamp expires
            if len(self._timestamps) >= self.max_requests:
                wait_time = self._timestamps[0] + self.window_seconds - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self._timestamps.popleft()

            self._timestamps.append(time.monotonic())

    def reset(self) -> None:
        """Reset the rate limiter."""
        self._timestamps.clear()
