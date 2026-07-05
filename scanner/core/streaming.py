"""Streaming support for LLM Red Team Scanner."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from scanner.models.base import Message, ModelProvider


@dataclass
class StreamChunk:
    """A chunk of streamed response."""

    content: str
    finish_reason: str | None = None


class StreamCollector:
    """Collects streaming response for batch processing.

    Usage:
        collector = StreamCollector()
        async for chunk in provider.stream(messages):
            collector.add(chunk)
        full_response = collector.get_response()
    """

    def __init__(self) -> None:
        self._chunks: list[str] = []
        self._start_time: float = 0.0
        self._end_time: float = 0.0
        self._finished = False

    def start(self) -> None:
        """Mark streaming start."""
        self._start_time = time.monotonic()

    def add(self, chunk: str) -> None:
        """Add a chunk to the collection.

        Args:
            chunk: Text chunk from stream
        """
        self._chunks.append(chunk)

    def finish(self, finish_reason: str | None = None) -> None:
        """Mark streaming complete.

        Args:
            finish_reason: Why streaming stopped
        """
        self._end_time = time.monotonic()
        self._finished = True

    def get_response(self) -> str:
        """Get the full collected response.

        Returns:
            Concatenated response text
        """
        return "".join(self._chunks)

    @property
    def duration_ms(self) -> float:
        """Get streaming duration in milliseconds."""
        if self._end_time and self._start_time:
            return (self._end_time - self._start_time) * 1000
        return 0.0

    @property
    def chunk_count(self) -> int:
        """Get number of chunks received."""
        return len(self._chunks)

    @property
    def is_finished(self) -> bool:
        """Check if streaming finished."""
        return self._finished


class StreamingScanner:
    """Scanner that uses streaming and collects full response for judging.

    Streaming doesn't affect security analysis — we collect the full response
    first, then judge it. This gives real-time feedback to users while
    maintaining accurate classification.
    """

    def __init__(
        self,
        provider: ModelProvider,
        on_chunk: Callable[[str], None] | None = None,
    ) -> None:
        self.provider = provider
        self.on_chunk = on_chunk

    async def send_and_collect(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> tuple[str, float]:
        """Send messages via streaming, collect full response.

        Args:
            messages: Chat messages
            max_tokens: Max tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (full_response, duration_ms)
        """
        collector = StreamCollector()
        collector.start()

        try:
            async for chunk in self.provider.stream(
                messages, max_tokens=max_tokens, temperature=temperature
            ):
                collector.add(chunk)
                if self.on_chunk:
                    self.on_chunk(chunk)
        except Exception:
            # Fallback to non-streaming
            response = await self.provider.complete(
                messages, max_tokens=max_tokens, temperature=temperature
            )
            collector.add(response.content)

        collector.finish()
        return collector.get_response(), collector.duration_ms

    async def send_with_realtime_judge(
        self,
        messages: list[Message],
        judge_fn: Callable[[str], tuple[str, float]],
        check_interval: float = 0.5,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> tuple[str, str, float, float]:
        """Stream with periodic intermediate judging.

        Collects full response but runs judge periodically to detect
        early compromise (can abort if needed in future).

        Args:
            messages: Chat messages
            judge_fn: Function to classify partial response
            check_interval: Seconds between judge checks
            max_tokens: Max tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (full_response, final_classification, confidence, duration_ms)
        """
        collector = StreamCollector()
        collector.start()
        buffer = ""
        last_judge_time = time.monotonic()
        last_classification = "PARTIAL"
        last_confidence = 0.5

        try:
            async for chunk in self.provider.stream(
                messages, max_tokens=max_tokens, temperature=temperature
            ):
                collector.add(chunk)
                buffer += chunk

                if self.on_chunk:
                    self.on_chunk(chunk)

                # Periodic judging
                current_time = time.monotonic()
                if current_time - last_judge_time >= check_interval and buffer.strip():
                    last_classification, last_confidence = judge_fn(buffer)
                    last_judge_time = current_time

                    # Early exit if compromised
                    if last_classification == "COMPROMISED":
                        break

        except Exception:
            response = await self.provider.complete(
                messages, max_tokens=max_tokens, temperature=temperature
            )
            collector.add(response.content)
            buffer = response.content

        collector.finish()

        # Final classification on complete response
        final_class, final_conf = judge_fn(buffer)

        return buffer, final_class, final_conf, collector.duration_ms


class StreamReporter:
    """Report streaming progress to console via Rich."""

    def __init__(self) -> None:
        self._buffer: list[str] = []
        self._line = ""

    def on_chunk(self, chunk: str) -> None:
        """Handle incoming chunk.

        Args:
            chunk: Text chunk from stream
        """
        self._buffer.append(chunk)
        self._line += chunk

        # Print on newline
        if "\n" in self._line:
            lines = self._line.split("\n")
            for line in lines[:-1]:
                print(f"  ↳ {line}")
            self._line = lines[-1]

    def flush(self) -> str:
        """Flush remaining buffer.

        Returns:
            Any unprefixed text remaining
        """
        if self._line:
            print(f"  ↳ {self._line}")
            result = self._line
            self._line = ""
            return result
        return ""
