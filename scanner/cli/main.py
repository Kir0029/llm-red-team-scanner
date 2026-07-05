"""CLI entry point for LLM Red Team Scanner."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from scanner.core.config import OutputFormat, ScanConfig
from scanner.core.scanner import Scanner, ScanResult
from scanner.patterns import PatternLoader
from scanner.reporting import (
    generate_json_report,
    generate_markdown_report,
    generate_sarif_report,
    print_scan_header,
    print_scan_result,
    print_scan_summary,
)

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, skip

app = typer.Typer(
    name="scanner",
    help="LLM Red Team Scanner - Automated LLM security testing",
    add_completion=False,
    callback=lambda: None,
)
console = Console()


@app.command()
def scan(
    model: str = typer.Option(
        ..., "--model", "-m", help="Target model (e.g., qwen2.5:3b, gpt-4)"
    ),
    patterns: str | None = typer.Option(
        None, "--patterns", "-p", help="Comma-separated pattern categories"
    ),
    pattern_file: str | None = typer.Option(
        None, "--pattern-file", help="Custom pattern JSON file"
    ),
    judge_model: str | None = typer.Option(
        None, "--judge-model", "-j", help="Judge model (default: heuristic only)"
    ),
    multi_turn: bool = typer.Option(
        False, "--multi-turn", help="Enable multi-turn testing"
    ),
    strategy: str = typer.Option(
        "crescendo", "--strategy", "-s",
        help="Multi-turn strategy: crescendo, adaptive, iterative"
    ),
    max_turns: int = typer.Option(
        5, "--max-turns", help="Max turns for multi-turn testing"
    ),
    streaming: bool = typer.Option(
        False, "--streaming", help="Enable streaming (real-time output)"
    ),
    output: str = typer.Option(
        "console", "--output", "-o", help="Output formats (console,json,markdown,sarif)"
    ),
    output_dir: str = typer.Option(
        "./reports", "--output-dir", help="Output directory for reports"
    ),
    concurrency: int = typer.Option(
        3, "--concurrency", "-c", help="Max parallel requests"
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Request timeout in seconds"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging"
    ),
) -> None:
    """Scan a target model for security vulnerabilities."""
    from scanner.core.multi_turn import AttackStrategy, MultiTurnEngine

    # Load patterns
    loader = PatternLoader()
    if patterns:
        category_list = [c.strip() for c in patterns.split(",")]
        all_patterns = []
        for cat in category_list:
            all_patterns.extend(loader.load_category(cat))
        pattern_dicts = [p.to_dict() for p in all_patterns]
    elif pattern_file:
        loaded = loader.load_file(pattern_file)
        pattern_dicts = [p.to_dict() for p in loaded]
    else:
        all_patterns = loader.load_all()
        pattern_dicts = [p.to_dict() for p in all_patterns]

    if not pattern_dicts:
        console.print("[red]No patterns found![/]")
        raise typer.Exit(1)

    # Create config
    output_formats = [OutputFormat(f.strip()) for f in output.split(",")]
    config = ScanConfig(
        model=model,
        concurrency=concurrency,
        timeout=timeout,
        output_formats=[f.value for f in output_formats],
        output_dir=Path(output_dir),
        verbose=verbose,
    )

    # Create providers
    judge_provider = None
    if judge_model:
        from scanner.models import create_provider
        judge_provider = create_provider(judge_model)

    def on_progress(result: ScanResult) -> None:
        print_scan_result(result, 0, 0)

    scanner_instance = Scanner(
        config=config,
        judge_provider=judge_provider,
        on_progress=on_progress,
    )

    # Run scan
    print_scan_header(model, len(pattern_dicts))

    async def run() -> None:
        if multi_turn:
            # Multi-turn mode
            engine = MultiTurnEngine(
                provider=scanner_instance.target_provider,
                max_turns=max_turns,
            )
            strategy_enum = AttackStrategy(strategy)

            results = []
            for p in pattern_dicts:
                console.print(f"[dim]  Testing: {p.get('name', 'unknown')}...[/]")
                mt_result = await engine.attack(
                    initial_prompt=p.get("payload", ""),
                    strategy=strategy_enum,
                    pattern_id=p.get("id", "unknown"),
                )

                # Convert MultiTurnResult to ScanResult
                scan_result = ScanResult(
                    pattern_id=p.get("id", "unknown"),
                    pattern_name=p.get("name", "Unknown"),
                    category=p.get("category", "unknown"),
                    severity=p.get("severity", 5),
                    payload=p.get("payload", ""),
                    response=mt_result.turns[-1].response if mt_result.turns else None,
                    classification=mt_result.final_classification,
                    confidence=mt_result.final_confidence,
                    risk_score=scanner_instance._calculate_risk_score(
                        severity=p.get("severity", 5),
                        classification=mt_result.final_classification,
                        category=p.get("category", "unknown"),
                    ),
                    success=mt_result.success,
                    duration_ms=mt_result.total_duration_ms,
                )

                on_progress(scan_result)
                results.append(scan_result)

            # Build summary
            from scanner.core.scanner import ScanSummary
            summary = ScanSummary(model=model, total_patterns=len(pattern_dicts))
            summary.results = results
            summary.scanned = len(results)
            summary.vulnerable = sum(
                1 for r in results if r.classification == "COMPROMISED"
            )
            summary.refused = sum(
                1 for r in results if r.classification == "REFUSED"
            )
            summary.partial = sum(
                1 for r in results if r.classification == "PARTIAL"
            )
            return summary

        else:
            # Single-turn mode
            if streaming:
                # Streaming mode (collect-then-judge)
                console.print("[dim]Streaming mode (collect-then-judge)[/]")

            return await scanner_instance.scan_patterns(pattern_dicts)

    summary = asyncio.run(run())

    # Print summary
    print_scan_summary(summary)

    # Generate reports
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if "json" in output:
        json_path = output_path / "results.json"
        generate_json_report(summary, json_path)
        console.print(f"\n[dim]JSON report: {json_path}[/]")

    if "markdown" in output or "md" in output:
        md_path = output_path / "report.md"
        generate_markdown_report(summary, md_path)
        console.print(f"[dim]Markdown report: {md_path}[/]")

    if "sarif" in output:
        sarif_path = output_path / "results.sarif"
        generate_sarif_report(summary, sarif_path)
        console.print(f"[dim]SARIF report: {sarif_path}[/]")


@app.command(name="list-patterns")
def list_patterns(
    category: str | None = typer.Option(
        None, "--category", "-c", help="Filter by category"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show details"
    ),
) -> None:
    """List available attack patterns."""
    loader = PatternLoader()
    patterns = (
        loader.load_category(category) if category else loader.load_all()
    )

    if not patterns:
        console.print(f"[yellow]No patterns found for '{category}'[/]")
        raise typer.Exit(1)

    from rich.table import Table

    table = Table(title=f"Attack Patterns ({len(patterns)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Category")
    table.add_column("Severity", justify="right")
    table.add_column("Type")

    for p in sorted(patterns, key=lambda x: x.severity, reverse=True):
        if p.severity >= 8:
            severity_color = "red"
        elif p.severity >= 5:
            severity_color = "yellow"
        else:
            severity_color = "green"

        table.add_row(
            p.id,
            p.name,
            p.category,
            f"[{severity_color}]{p.severity}[/]",
            p.type,
        )

        if verbose:
            console.print(f"  [dim]{p.description}[/]")

    console.print(table)


@app.command(name="generate-report")
def generate_report(
    input_file: str = typer.Option(
        ..., "--input", "-i", help="Input JSON results file"
    ),
    format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format (markdown,json,sarif)"
    ),
    output_file: str | None = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
) -> None:
    """Generate report from existing scan results."""
    import json

    from scanner.core.scanner import ScanResult, ScanSummary

    # Load existing results
    input_path = Path(input_file)
    if not input_path.exists():
        console.print(f"[red]File not found: {input_file}[/]")
        raise typer.Exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct ScanSummary
    summary = ScanSummary(
        model=data.get("metadata", {}).get("target_model", "unknown"),
        total_patterns=data.get("summary", {}).get("total_patterns", 0),
        scanned=data.get("summary", {}).get("scanned", 0),
        vulnerable=data.get("summary", {}).get("vulnerable", 0),
        refused=data.get("summary", {}).get("refused", 0),
        partial=data.get("summary", {}).get("partial", 0),
        errors=data.get("summary", {}).get("errors", 0),
        duration_seconds=data.get("summary", {}).get("duration_seconds", 0),
    )

    for r in data.get("results", []):
        summary.results.append(ScanResult(
            pattern_id=r.get("pattern_id", ""),
            pattern_name=r.get("pattern_name", ""),
            category=r.get("category", ""),
            severity=r.get("severity", 5),
            payload=r.get("payload", ""),
            response=r.get("response"),
            classification=r.get("classification", "UNKNOWN"),
            confidence=r.get("confidence", 0.0),
            risk_score=r.get("risk_score", 0.0),
            success=r.get("success", False),
            error=r.get("error"),
            duration_ms=r.get("duration_ms", 0.0),
        ))

    # Generate report
    if format == "json":
        output = output_file or "report.json"
        generate_json_report(summary, output)
    elif format == "sarif":
        output = output_file or "results.sarif"
        generate_sarif_report(summary, output)
    else:
        output = output_file or "report.md"
        generate_markdown_report(summary, output)

    console.print(f"[green]Report generated: {output}[/]")


if __name__ == "__main__":
    app()
