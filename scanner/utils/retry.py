"""Retry utility with exponential backoff for LLM Red Team Scanner."""

import asyncio
import random
from collections.abc import Callable
from typing import Any, TypeVar

from scanner.core.exceptions import RateLimitError, TimeoutError

T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (RateLimitError, TimeoutError),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for retrying failed operations with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
        max_delay: Maximum delay in seconds
        retryable_exceptions: Tuple of exceptions that trigger retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2**attempt), max_delay)
                        jitter = random.uniform(0, delay * 0.1)
                        await asyncio.sleep(delay + jitter)

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
