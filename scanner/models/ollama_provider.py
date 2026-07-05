"""Ollama LLM provider for local models."""

import builtins
from collections.abc import AsyncIterator

import ollama as ollama_lib

from scanner.core.exceptions import ProviderError, TimeoutError
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class OllamaProvider(ModelProvider):
    """Provider for local Ollama models.

    Supports both complete and streaming.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
    ) -> None:
        super().__init__(model=model, provider_type=ProviderType.OLLAMA)
        self.base_url = base_url
        self._client = ollama_lib.AsyncClient(host=base_url)

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Send completion request to Ollama.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            ModelResponse with generated content
        """
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            response = await self._client.chat(
                model=self.model,
                messages=ollama_messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )

            content = response.get("message", {}).get("content", "")
            total_tokens = response.get("eval_count", 0) + response.get(
                "prompt_eval_count", 0
            )

            return ModelResponse(
                content=content,
                model=self.model,
                provider=self.provider_type,
                usage={
                    "total_tokens": total_tokens,
                    "prompt_tokens": response.get("prompt_eval_count", 0),
                    "completion_tokens": response.get("eval_count", 0),
                },
                finish_reason="stop" if response.get("done") else "length",
                raw=response,
            )

        except ollama_lib.ResponseError as e:
            if "not found" in str(e).lower():
                raise ProviderError(
                    f"Model '{self.model}' not found. Run: ollama pull {self.model}"
                ) from e
            raise ProviderError(f"Ollama error: {e}") from e
        except builtins.TimeoutError as e:
            raise TimeoutError(
                f"Ollama request timed out for model '{self.model}'"
            ) from e

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream tokens from Ollama.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            async for chunk in await self._client.chat(
                model=self.model,
                messages=ollama_messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
                stream=True,
            ):
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

                if chunk.get("done"):
                    break

        except ollama_lib.ResponseError as e:
            raise ProviderError(f"Ollama streaming error: {e}") from e

    async def health_check(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            models = await self._client.list()
            available = [m.get("name", "") for m in models.get("models", [])]
            return self.model in available or f"{self.model}:latest" in available
        except Exception:
            return False
