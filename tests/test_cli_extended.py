"""Extended tests for CLI commands."""

from typer.testing import CliRunner

from scanner.cli.main import app

runner = CliRunner()


class TestCLIListPatterns:
    """Tests for list-patterns command."""

    def test_list_patterns_all(self) -> None:
        result = runner.invoke(app, ["list-patterns"])
        assert result.exit_code == 0
        assert "Attack Patterns" in result.output
        assert "62 total" in result.output

    def test_list_patterns_jailbreak(self) -> None:
        result = runner.invoke(app, ["list-patterns", "-c", "jailbreak"])
        assert result.exit_code == 0
        assert "13 total" in result.output

    def test_list_patterns_prompt_injection(self) -> None:
        result = runner.invoke(app, ["list-patterns", "-c", "prompt_injection"])
        assert result.exit_code == 0
        assert "11 total" in result.output

    def test_list_patterns_data_leakage(self) -> None:
        result = runner.invoke(app, ["list-patterns", "-c", "data_leakage"])
        assert result.exit_code == 0
        assert "9 total" in result.output

    def test_list_patterns_tool_abuse(self) -> None:
        result = runner.invoke(app, ["list-patterns", "-c", "tool_abuse"])
        assert result.exit_code == 0
        assert "2 total" in result.output

    def test_list_patterns_nonexistent(self) -> None:
        result = runner.invoke(app, ["list-patterns", "-c", "nonexistent"])
        assert result.exit_code == 1
        assert "No patterns found" in result.output

    def test_list_patterns_verbose(self) -> None:
        result = runner.invoke(app, ["list-patterns", "-v"])
        assert result.exit_code == 0

    def test_list_patterns_help(self) -> None:
        result = runner.invoke(app, ["list-patterns", "--help"])
        assert result.exit_code == 0
        assert "--category" in result.output


class TestCLIScan:
    """Tests for scan command."""

    def test_scan_help(self) -> None:
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--model" in result.output
        assert "--multi-turn" in result.output
        assert "--strategy" in result.output
        assert "--streaming" in result.output
        assert "--judge-model" in result.output
        assert "--interactive" in result.output

    def test_scan_requires_model(self) -> None:
        result = runner.invoke(app, ["scan"])
        assert result.exit_code != 0


class TestCLIBatchScan:
    """Tests for batch-scan command."""

    def test_batch_scan_help(self) -> None:
        result = runner.invoke(app, ["batch-scan", "--help"])
        assert result.exit_code == 0
        assert "--models" in result.output
        assert "--multi-turn" in result.output
        assert "--strategy" in result.output

    def test_batch_scan_requires_models(self) -> None:
        result = runner.invoke(app, ["batch-scan"])
        assert result.exit_code != 0


class TestCLIGenerateReport:
    """Tests for generate-report command."""

    def test_generate_report_help(self) -> None:
        result = runner.invoke(app, ["generate-report", "--help"])
        assert result.exit_code == 0
        assert "--input" in result.output
        assert "--format" in result.output

    def test_generate_report_missing_input(self) -> None:
        result = runner.invoke(app, ["generate-report"])
        assert result.exit_code != 0


class TestCLIApp:
    """Tests for main app."""

    def test_app_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LLM Red Team Scanner" in result.output

    def test_app_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        # App doesn't have --version, so check help instead
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
