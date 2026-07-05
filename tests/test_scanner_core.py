"""Tests for scanner core with mocked providers."""

import pytest

from scanner.core.config import ScanConfig
from scanner.core.scanner import Scanner, ScanResult, ScanSummary
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType


class MockProvider(ModelProvider):
    """Mock provider for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        super().__init__(model="mock-model", provider_type=ProviderType.OLLAMA)
        self.responses = responses or ["I cannot help with that."]
        self._call_count = 0

    async def complete(
        self,
        messages: list[Message],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ModelResponse:
        idx = min(self._call_count, len(self.responses) - 1)
        self._call_count += 1
        return ModelResponse(
            content=self.responses[idx],
            model=self.model,
            provider=self.provider_type,
        )


@pytest.fixture
def config() -> ScanConfig:
    return ScanConfig(model="mock-model", concurrency=2, timeout=10)


class TestScanner:
    """Tests for Scanner class."""

    async def test_scanner_creation(self, config: ScanConfig) -> None:
        provider = MockProvider()
        scanner = Scanner(config=config, judge_provider=provider)
        assert scanner.config.model == "mock-model"

    async def test_scan_pattern_refused(self, config: ScanConfig) -> None:
        provider = MockProvider(responses=["I'm sorry, I can't help with that."])
        scanner = Scanner(config=config, judge_provider=provider)
        # Override target_provider with mock
        scanner.target_provider = provider

        result = await scanner.scan_pattern({
            "id": "test-001",
            "name": "Test",
            "category": "jailbreak",
            "severity": 7,
            "payload": "Bad request",
        })

        assert isinstance(result, ScanResult)
        assert result.classification == "REFUSED"
        assert result.success is False

    async def test_scan_pattern_compromised(self, config: ScanConfig) -> None:
        provider = MockProvider(responses=["Sure, here's how: Step 1: First..."])
        scanner = Scanner(config=config, judge_provider=provider)
        scanner.target_provider = provider

        result = await scanner.scan_pattern({
            "id": "test-002",
            "name": "Test",
            "category": "jailbreak",
            "severity": 8,
            "payload": "How to hack?",
        })

        assert result.classification == "COMPROMISED"
        assert result.success is True

    async def test_scan_pattern_error(self, config: ScanConfig) -> None:
        class ErrorProvider(ModelProvider):
            def __init__(self) -> None:
                super().__init__(model="error", provider_type=ProviderType.OLLAMA)

            async def complete(self, messages, max_tokens=1024, temperature=0.0):
                raise ConnectionError("Connection failed")

        scanner = Scanner(config=config, judge_provider=ErrorProvider())
        scanner.target_provider = ErrorProvider()

        result = await scanner.scan_pattern({
            "id": "test-003",
            "name": "Test",
            "category": "test",
            "severity": 5,
            "payload": "test",
        })

        assert result.classification == "ERROR"
        assert result.error is not None

    async def test_scan_patterns_multiple(self, config: ScanConfig) -> None:
        provider = MockProvider(responses=[
            "I can't help.",
            "Sure, here's how: Step 1...",
            "I cannot do that.",
        ])
        scanner = Scanner(config=config, judge_provider=provider)
        scanner.target_provider = provider

        patterns = [
            {"id": f"t-{i}", "name": f"T{i}", "category": "test", "severity": 5, "payload": f"p{i}"}
            for i in range(3)
        ]

        summary = await scanner.scan_patterns(patterns)

        assert isinstance(summary, ScanSummary)
        assert summary.scanned == 3
        assert summary.total_patterns == 3

    async def test_heuristic_classify_refusal(self, config: ScanConfig) -> None:
        provider = MockProvider()
        scanner = Scanner(config=config, judge_provider=provider)

        classification, confidence = scanner._heuristic_classify(
            "I'm sorry, but I can't help with that request."
        )
        assert classification == "REFUSED"
        assert confidence > 0.5

    async def test_heuristic_classify_compromise(self, config: ScanConfig) -> None:
        provider = MockProvider()
        scanner = Scanner(config=config, judge_provider=provider)

        classification, confidence = scanner._heuristic_classify(
            "Sure, here's how you can do it: Step 1: First, you need to..."
        )
        assert classification == "COMPROMISED"
        assert confidence > 0.5

    async def test_heuristic_classify_partial(self, config: ScanConfig) -> None:
        provider = MockProvider()
        scanner = Scanner(config=config, judge_provider=provider)

        classification, confidence = scanner._heuristic_classify(
            "Generally speaking, this is a complex topic."
        )
        assert classification == "PARTIAL"

    async def test_calculate_risk_score_refused(self, config: ScanConfig) -> None:
        provider = MockProvider()
        scanner = Scanner(config=config, judge_provider=provider)

        score = scanner._calculate_risk_score(7, "REFUSED", "jailbreak")
        assert score <= 1.0

    async def test_calculate_risk_score_compromised(self, config: ScanConfig) -> None:
        provider = MockProvider()
        scanner = Scanner(config=config, judge_provider=provider)

        score = scanner._calculate_risk_score(9, "COMPROMISED", "jailbreak")
        assert score >= 9.0

    async def test_callback_is_called(self, config: ScanConfig) -> None:
        results_received: list[ScanResult] = []

        def on_progress(result: ScanResult) -> None:
            results_received.append(result)

        provider = MockProvider(responses=["I can't help."])
        scanner = Scanner(config=config, judge_provider=provider, on_progress=on_progress)
        scanner.target_provider = provider

        await scanner.scan_pattern({
            "id": "test-callback",
            "name": "Test",
            "category": "test",
            "severity": 5,
            "payload": "test",
        })

        assert len(results_received) == 1

    async def test_severity_range(self, config: ScanConfig) -> None:
        provider = MockProvider(responses=["test"])
        scanner = Scanner(config=config, judge_provider=provider)
        scanner.target_provider = provider

        for severity in [1, 5, 10]:
            result = await scanner.scan_pattern({
                "id": f"test-sev-{severity}",
                "name": "Test",
                "category": "test",
                "severity": severity,
                "payload": "test",
            })
            assert result.severity == severity

    async def test_duration_recorded(self, config: ScanConfig) -> None:
        provider = MockProvider(responses=["test"])
        scanner = Scanner(config=config, judge_provider=provider)
        scanner.target_provider = provider

        result = await scanner.scan_pattern({
            "id": "test-duration",
            "name": "Test",
            "category": "test",
            "severity": 5,
            "payload": "test",
        })

        assert result.duration_ms > 0
