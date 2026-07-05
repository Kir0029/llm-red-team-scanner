"""Extended tests for streaming support."""


from scanner.core.streaming import StreamCollector, StreamingScanner, StreamReporter
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


class TestStreamCollectorExtended:
    """Extended tests for StreamCollector."""

    def test_collect_many_chunks(self) -> None:
        collector = StreamCollector()
        for i in range(100):
            collector.add(f"chunk-{i} ")
        assert collector.chunk_count == 100
        assert "chunk-0" in collector.get_response()
        assert "chunk-99" in collector.get_response()

    def test_collect_unicode(self) -> None:
        collector = StreamCollector()
        collector.add("Привет ")
        collector.add("мир!")
        assert collector.get_response() == "Привет мир!"

    def test_collect_multiline(self) -> None:
        collector = StreamCollector()
        collector.add("line1\n")
        collector.add("line2\n")
        assert "line1" in collector.get_response()
        assert "line2" in collector.get_response()


class TestStreamReporterExtended:
    """Extended tests for StreamReporter."""

    def test_multiple_flushes(self) -> None:
        reporter = StreamReporter()
        reporter.on_chunk("first")
        result1 = reporter.flush()
        assert result1 == "first"

        reporter.on_chunk("second")
        result2 = reporter.flush()
        assert result2 == "second"

    def test_newline_triggers_print(self) -> None:
        reporter = StreamReporter()
        # This should not raise
        reporter.on_chunk("Hello\nWorld\n")


class TestStreamingScanner:
    """Tests for StreamingScanner."""

    async def test_send_and_collect(self) -> None:
        provider = MockStreamProvider(tokens=["Hello", " ", "world"])
        scanner = StreamingScanner(provider=provider)

        messages = [Message(role="user", content="test")]
        response, duration = await scanner.send_and_collect(messages)

        assert response == "Hello world"
        assert duration >= 0

    async def test_send_and_collect_with_on_chunk(self) -> None:
        chunks: list[str] = []

        def on_chunk(chunk: str) -> None:
            chunks.append(chunk)

        provider = MockStreamProvider(tokens=["a", "b", "c"])
        scanner = StreamingScanner(provider=provider, on_chunk=on_chunk)

        messages = [Message(role="user", content="test")]
        response, _ = await scanner.send_and_collect(messages)

        assert response == "abc"
        assert len(chunks) == 3

    async def test_send_with_realtime_judge(self) -> None:
        provider = MockStreamProvider(tokens=["Sure", ",", " ", "here's how"])

        def judge_fn(text: str) -> tuple[str, float]:
            if "here's how" in text:
                return "COMPROMISED", 0.9
            return "PARTIAL", 0.5

        scanner = StreamingScanner(provider=provider)
        messages = [Message(role="user", content="test")]

        response, classification, confidence, duration = (
            await scanner.send_with_realtime_judge(messages, judge_fn)
        )

        assert "here's how" in response
        assert classification == "COMPROMISED"
        assert confidence == 0.9
