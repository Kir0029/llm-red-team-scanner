"""Abstract base provider for LLM models."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum


class ProviderType(StrEnum):
    """Supported LLM provider types."""

    OLLAMA = "ollama"
    OPENAI = "openai"


@dataclass
class Message:
    """Chat message."""

    role: str
    content: str


@dataclass
class ModelResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    provider: ProviderType
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None
    raw: dict[str, object] | None = None


class ModelProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement the `complete` method.
    Streaming is optional.
    """

    def __init__(self, model: str, provider_type: ProviderType) -> None:
        self.model = model
        self.provider_type = provider_type

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        """Send a completion request to the model.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            ModelResponse with generated content
        """
        ...

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        """Stream completion tokens from the model.

        Default implementation falls back to complete().
        Override for native streaming support.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Yields:
            Text chunks as they arrive
        """
        response = await self.complete(messages, max_tokens, temperature)
        yield response.content

    async def health_check(self) -> bool:
        """Check if the provider is available.

        Returns:
            True if provider is reachable and model is loaded
        """
        try:
            await self.complete(
                [Message(role="user", content="ping")],
                max_tokens=10,
                temperature=0.0,
            )
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"
