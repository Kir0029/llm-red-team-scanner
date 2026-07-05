"""Tests for utility modules."""

import pytest

from scanner.core.exceptions import RateLimitError, TimeoutError
from scanner.utils.rate_limiter import RateLimiter
from scanner.utils.retry import retry
from scanner.utils.validators import (
    validate_concurrency,
    validate_model_name,
)


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_creation(self) -> None:
        limiter = RateLimiter(max_requests=5, window_seconds=1.0)
        assert limiter.max_requests == 5
        assert limiter.window_seconds == 1.0

    async def test_acquire_within_limit(self) -> None:
        limiter = RateLimiter(max_requests=5, window_seconds=1.0)
        # Should not block
        await limiter.acquire()

    async def test_acquire_multiple(self) -> None:
        limiter = RateLimiter(max_requests=3, window_seconds=1.0)
        for _ in range(3):
            await limiter.acquire()


class TestRetry:
    """Tests for retry decorator."""

    async def test_success_no_retry(self) -> None:
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    async def test_retry_on_rate_limit_error(self) -> None:
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limited")
            return "success"

        result = await fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    async def test_retry_on_timeout_error(self) -> None:
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timed out")
            return "success"

        result = await fail_then_succeed()
        assert result == "success"
        assert call_count == 2

    async def test_max_attempts_exceeded(self) -> None:
        @retry(max_attempts=2, base_delay=0.01)
        async def always_fail() -> str:
            raise RateLimitError("Permanent failure")

        with pytest.raises(RateLimitError, match="Permanent failure"):
            await always_fail()

    async def test_no_retry_on_value_error(self) -> None:
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def value_error_func() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            await value_error_func()
        assert call_count == 1


class TestValidators:
    """Tests for validator functions."""

    def test_validate_model_name_valid(self) -> None:
        assert validate_model_name("qwen2.5:3b") == "qwen2.5:3b"
        assert validate_model_name("gpt-4") == "gpt-4"
        assert validate_model_name("claude-3-opus") == "claude-3-opus"

    def test_validate_model_name_empty(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_model_name("")

    def test_validate_model_name_none(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_model_name(None)  # type: ignore[arg-type]

    def test_validate_model_name_whitespace(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_model_name("   ")

    def test_validate_concurrency_valid(self) -> None:
        assert validate_concurrency(1) == 1
        assert validate_concurrency(5) == 5
        assert validate_concurrency(20) == 20

    def test_validate_concurrency_too_low(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            validate_concurrency(0)

    def test_validate_concurrency_too_high(self) -> None:
        with pytest.raises(ValueError, match="cannot exceed 20"):
            validate_concurrency(21)
