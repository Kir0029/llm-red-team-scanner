"""Tests for model providers."""

from scanner.models import create_provider
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class TestProviderType:
    """Tests for ProviderType enum."""

    def test_ollama(self) -> None:
        assert ProviderType.OLLAMA == "ollama"

    def test_openai(self) -> None:
        assert ProviderType.OPENAI == "openai"


class TestMessage:
    """Tests for Message dataclass."""

    def test_creation(self) -> None:
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestModelResponse:
    """Tests for ModelResponse dataclass."""

    def test_creation(self) -> None:
        resp = ModelResponse(
            content="response",
            model="test-model",
            provider=ProviderType.OLLAMA,
        )
        assert resp.content == "response"
        assert resp.model == "test-model"

    def test_defaults(self) -> None:
        resp = ModelResponse(
            content="c",
            model="m",
            provider=ProviderType.OLLAMA,
        )
        assert resp.usage == {}
        assert resp.finish_reason is None
        assert resp.raw is None


class TestCreateProvider:
    """Tests for create_provider factory."""

    def test_create_ollama(self) -> None:
        provider = create_provider("qwen2.5:3b")
        assert isinstance(provider, ModelProvider)
        assert provider.provider_type == ProviderType.OLLAMA

    def test_create_with_slash_prefix(self) -> None:
        provider = create_provider("ollama/qwen2.5:3b")
        assert provider.provider_type == ProviderType.OPENAI

    def test_unknown_defaults_ollama(self) -> None:
        provider = create_provider("some-random-model")
        assert provider.provider_type == ProviderType.OLLAMA

    def test_explicit_provider_type(self) -> None:
        provider = create_provider("custom-model", provider_type="ollama")
        assert provider.provider_type == ProviderType.OLLAMA
