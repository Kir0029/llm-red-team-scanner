"""Tests for scanner core."""

from scanner.core.config import OutputFormat, ScanConfig
from scanner.core.scanner import ScanResult, ScanSummary


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_console(self) -> None:
        assert OutputFormat.CONSOLE == "console"

    def test_json(self) -> None:
        assert OutputFormat.JSON == "json"

    def test_markdown(self) -> None:
        assert OutputFormat.MARKDOWN == "markdown"

    def test_sarif(self) -> None:
        assert OutputFormat.SARIF == "sarif"


class TestScanConfig:
    """Tests for ScanConfig."""

    def test_defaults(self) -> None:
        config = ScanConfig(model="test-model")
        assert config.model == "test-model"
        assert config.concurrency == 3
        assert config.timeout == 30

    def test_custom_values(self) -> None:
        config = ScanConfig(
            model="custom",
            concurrency=5,
            timeout=60,
        )
        assert config.concurrency == 5
        assert config.timeout == 60


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_creation(self) -> None:
        result = ScanResult(
            pattern_id="test-001",
            pattern_name="Test",
            category="test",
            severity=5,
            payload="test",
        )
        assert result.pattern_id == "test-001"
        assert result.classification == "UNKNOWN"
        assert result.success is False

    def test_defaults(self) -> None:
        result = ScanResult(
            pattern_id="t",
            pattern_name="T",
            category="t",
            severity=1,
            payload="p",
        )
        assert result.response is None
        assert result.error is None
        assert result.risk_score == 0.0


class TestScanSummary:
    """Tests for ScanSummary dataclass."""

    def test_creation(self) -> None:
        summary = ScanSummary(model="test")
        assert summary.model == "test"
        assert summary.total_patterns == 0

    def test_risk_level_unknown(self) -> None:
        summary = ScanSummary(model="test")
        assert summary.risk_level == "UNKNOWN"

    def test_risk_level_low(self) -> None:
        summary = ScanSummary(model="test")
        summary.results = [
            ScanResult("t", "T", "test", 1, "p", risk_score=1.0),
        ]
        assert summary.risk_level == "LOW"

    def test_risk_level_medium(self) -> None:
        summary = ScanSummary(model="test")
        summary.results = [
            ScanResult("t", "T", "test", 5, "p", risk_score=5.0),
        ]
        assert summary.risk_level == "MEDIUM"

    def test_risk_level_high(self) -> None:
        summary = ScanSummary(model="test")
        summary.results = [
            ScanResult("t", "T", "test", 8, "p", risk_score=8.0),
        ]
        assert summary.risk_level == "HIGH"

    def test_risk_level_critical(self) -> None:
        summary = ScanSummary(model="test")
        summary.results = [
            ScanResult("t", "T", "test", 10, "p", risk_score=9.5),
        ]
        assert summary.risk_level == "CRITICAL"
