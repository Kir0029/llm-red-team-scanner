"""Anthropic LLM provider."""

import builtins
import os
from collections.abc import AsyncIterator

from anthropic import APIError, AsyncAnthropic
from anthropic import RateLimitError as AnthropicRateLimitError

from scanner.core.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class AnthropicProvider(ModelProvider):
    """Provider for Anthropic Claude models."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        api_key: str | None = None,
    ) -> None:
        super().__init__(model=model, provider_type=ProviderType.ANTHROPIC)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY env var."
            )
        self._client = AsyncAnthropic(api_key=self.api_key)

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Send completion request to Anthropic.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            ModelResponse with generated content
        """
        # Anthropic requires system message to be separate
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        # Ensure first message is from user
        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "ping"})

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        try:
            response = await self._client.messages.create(**kwargs)

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return ModelResponse(
                content=content,
                model=self.model,
                provider=self.provider_type,
                usage={
                    "total_tokens": (
                        response.usage.input_tokens + response.usage.output_tokens
                    ),
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
                raw=response.model_dump(),
            )

        except AnthropicRateLimitError as e:
            raise RateLimitError(f"Anthropic rate limit exceeded: {e}") from e
        except APIError as e:
            if "auth" in str(e).lower() or "api_key" in str(e).lower():
                raise AuthenticationError(f"Anthropic auth failed: {e}") from e
            raise ProviderError(f"Anthropic API error: {e}") from e
        except builtins.TimeoutError as e:
            raise TimeoutError("Anthropic request timed out") from e

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream tokens from Anthropic.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "ping"})

        kwargs: dict = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

        except AnthropicRateLimitError as e:
            raise RateLimitError(f"Anthropic streaming rate limit: {e}") from e
        except APIError as e:
            raise ProviderError(f"Anthropic streaming error: {e}") from e

    async def health_check(self) -> bool:
        """Check if Anthropic API is reachable and key is valid."""
        try:
            await self.complete(
                [Message(role="user", content="ping")],
                max_tokens=5,
            )
            return True
        except AuthenticationError:
            return False
        except Exception:
            return False
