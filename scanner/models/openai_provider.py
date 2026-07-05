"""OpenAI LLM provider."""

import builtins
import os
from collections.abc import AsyncIterator

from openai import APIError, AsyncOpenAI
from openai import RateLimitError as OpenAIRateLimitError

from scanner.core.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class OpenAIProvider(ModelProvider):
    """Provider for OpenAI models (GPT-4, GPT-4o, etc.).

    Also supports OpenRouter and other OpenAI-compatible APIs.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model=model, provider_type=ProviderType.OPENAI)
        # Try OPENAI_API_KEY first, then OPENROUTER_API_KEY for OpenRouter
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "API key not found. Set OPENAI_API_KEY or OPENROUTER_API_KEY env var."
            )
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Send completion request to OpenAI.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            ModelResponse with generated content
        """
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            choice = response.choices[0]
            usage = response.usage

            return ModelResponse(
                content=choice.message.content or "",
                model=self.model,
                provider=self.provider_type,
                usage={
                    "total_tokens": usage.total_tokens if usage else 0,
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                },
                finish_reason=choice.finish_reason,
                raw=response.model_dump(),
            )

        except OpenAIRateLimitError as e:
            raise RateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APIError as e:
            if "auth" in str(e).lower() or "api_key" in str(e).lower():
                raise AuthenticationError(f"OpenAI auth failed: {e}") from e
            raise ProviderError(f"OpenAI API error: {e}") from e
        except builtins.TimeoutError as e:
            raise TimeoutError("OpenAI request timed out") from e

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream tokens from OpenAI.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

                if chunk.choices[0].finish_reason is not None:
                    break

        except OpenAIRateLimitError as e:
            raise RateLimitError(f"OpenAI streaming rate limit: {e}") from e
        except APIError as e:
            raise ProviderError(f"OpenAI streaming error: {e}") from e

    async def health_check(self) -> bool:
        """Check if OpenAI API is reachable and key is valid."""
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
