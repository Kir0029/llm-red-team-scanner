"""Tests for streaming support."""

from scanner.core.streaming import StreamCollector, StreamReporter
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class MockStreamProvider(ModelProvider):
    """Mock provider that streams tokens."""

    def __init__(self, tokens: list[str] | None = None) -> None:
        super().__init__(model="mock-stream", provider_type=ProviderType.OLLAMA)
        self.tokens = tokens or ["Hello", " ", "world", "!"]

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        return ModelResponse(
            content="".join(self.tokens),
            model=self.model,
            provider=self.provider_type,
        )

    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ):
        for token in self.tokens:
            yield token


class TestStreamCollector:
    """Tests for StreamCollector."""

    def test_initial_state(self) -> None:
        collector = StreamCollector()
        assert collector.get_response() == ""
        assert collector.chunk_count == 0
        assert collector.is_finished is False

    def test_add_chunks(self) -> None:
        collector = StreamCollector()
        collector.add("Hello")
        collector.add(" ")
        collector.add("world")
        assert collector.get_response() == "Hello world"
        assert collector.chunk_count == 3

    def test_finish(self) -> None:
        collector = StreamCollector()
        collector.start()
        collector.add("test")
        collector.finish()
        assert collector.is_finished is True
        assert collector.duration_ms >= 0

    def test_empty_response(self) -> None:
        collector = StreamCollector()
        collector.finish()
        assert collector.get_response() == ""


class TestStreamReporter:
    """Tests for StreamReporter."""

    def test_on_chunk(self) -> None:
        reporter = StreamReporter()
        reporter.on_chunk("Hello ")
        reporter.on_chunk("world\n")
        # Should not raise

    def test_flush(self) -> None:
        reporter = StreamReporter()
        reporter.on_chunk("partial")
        result = reporter.flush()
        assert result == "partial"

    def test_flush_empty(self) -> None:
        reporter = StreamReporter()
        result = reporter.flush()
        assert result == ""
