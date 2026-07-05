"""Tests for CLI commands."""


from typer.testing import CliRunner

from scanner.cli.main import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI application."""

    def test_app_exists(self) -> None:
        assert app is not None

    def test_list_patterns(self) -> None:
        result = runner.invoke(app, ["list-patterns"])
        assert result.exit_code == 0
        assert "Attack Patterns" in result.output

    def test_list_patterns_jailbreak(self) -> None:
        result = runner.invoke(app, ["list-patterns", "--category", "jailbreak"])
        assert result.exit_code == 0
        assert "jailbreak" in result.output.lower() or "Jailbreak" in result.output

    def test_scan_help(self) -> None:
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output

    def test_generate_report_help(self) -> None:
        result = runner.invoke(app, ["generate-report", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
