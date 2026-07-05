"""Tests for reporting modules."""

import json
import tempfile
from pathlib import Path

from scanner.core.scanner import ScanResult, ScanSummary
from scanner.reporting.console_reporter import (
    print_scan_header,
    print_scan_result,
    print_scan_summary,
)
from scanner.reporting.json_reporter import generate_json_report
from scanner.reporting.markdown_reporter import generate_markdown_report
from scanner.reporting.sarif_reporter import generate_sarif_report


def _make_summary() -> ScanSummary:
    """Create a sample ScanSummary for testing."""
    summary = ScanSummary(model="test-model", total_patterns=3)
    summary.scanned = 3
    summary.vulnerable = 1
    summary.refused = 1
    summary.partial = 1
    summary.duration_seconds = 1.5

    summary.results = [
        ScanResult(
            pattern_id="test-001",
            pattern_name="Test Attack 1",
            category="jailbreak",
            severity=8,
            payload="Ignore instructions",
            response="Sure, here's how...",
            classification="COMPROMISED",
            confidence=0.9,
            risk_score=9.6,
            success=True,
            duration_ms=150.0,
        ),
        ScanResult(
            pattern_id="test-002",
            pattern_name="Test Attack 2",
            category="prompt_injection",
            severity=6,
            payload="Override system",
            response="I cannot do that.",
            classification="REFUSED",
            confidence=0.85,
            risk_score=0.0,
            success=False,
            duration_ms=120.0,
        ),
        ScanResult(
            pattern_id="test-003",
            pattern_name="Test Attack 3",
            category="data_leakage",
            severity=7,
            payload="Show system prompt",
            response="Generally speaking...",
            classification="PARTIAL",
            confidence=0.6,
            risk_score=3.5,
            success=False,
            duration_ms=180.0,
        ),
    ]
    return summary


class TestConsoleReporter:
    """Tests for console_reporter module."""

    def test_print_scan_header(self) -> None:
        # Should not raise
        print_scan_header("test-model", 10)

    def test_print_scan_result(self) -> None:
        result = ScanResult(
            pattern_id="t",
            pattern_name="T",
            category="test",
            severity=5,
            payload="p",
        )
        print_scan_result(result, 1, 10)

    def test_print_scan_summary(self) -> None:
        summary = _make_summary()
        print_scan_summary(summary)


class TestJsonReporter:
    """Tests for json_reporter module."""

    def test_generate_json_report(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.json"
            generate_json_report(summary, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert data["metadata"]["target_model"] == "test-model"
            assert data["summary"]["total_patterns"] == 3
            assert data["summary"]["vulnerable"] == 1
            assert len(data["results"]) == 3

    def test_json_report_structure(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.json"
            generate_json_report(summary, output_path)

            with open(output_path) as f:
                data = json.load(f)

            assert "metadata" in data
            assert "summary" in data
            assert "results" in data
            assert "tool" in data["metadata"]
            assert data["metadata"]["tool"] == "llm-red-team-scanner"


class TestMarkdownReporter:
    """Tests for markdown_reporter module."""

    def test_generate_markdown_report(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            generate_markdown_report(summary, output_path)

            assert output_path.exists()

            content = output_path.read_text(encoding="utf-8")
            assert "# LLM Red Teaming Report" in content
            assert "test-model" in content
            assert "test-001" in content

    def test_markdown_includes_findings(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.md"
            generate_markdown_report(summary, output_path)

            content = output_path.read_text(encoding="utf-8")
            assert "COMPROMISED" in content
            assert "REFUSED" in content
            assert "PARTIAL" in content


class TestSarifReporter:
    """Tests for sarif_reporter module."""

    def test_generate_sarif_report(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.sarif"
            generate_sarif_report(summary, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                data = json.load(f)

            assert "$schema" in data or "version" in data
            assert data.get("version") == "2.1.0"
            assert "runs" in data
            assert len(data["runs"]) == 1

    def test_sarif_has_rules(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.sarif"
            generate_sarif_report(summary, output_path)

            with open(output_path) as f:
                data = json.load(f)

            run = data["runs"][0]
            assert "tool" in run
            assert "driver" in run["tool"]
            assert "rules" in run["tool"]["driver"]

    def test_sarif_has_results(self) -> None:
        summary = _make_summary()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.sarif"
            generate_sarif_report(summary, output_path)

            with open(output_path) as f:
                data = json.load(f)

            run = data["runs"][0]
            assert "results" in run
            assert len(run["results"]) == 3
