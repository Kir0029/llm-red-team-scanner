"""CLI entry point for LLM Red Team Scanner."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from scanner.core.config import OutputFormat, ScanConfig
from scanner.core.scanner import Scanner, ScanResult, ScanSummary
from scanner.patterns import PatternLoader
from scanner.reporting import (
    generate_json_report,
    generate_markdown_report,
    generate_sarif_report,
    print_scan_header,
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


def _load_patterns(
    patterns: str | None,
    pattern_file: str | None,
    interactive: bool = False,
) -> list[dict]:
    """Load patterns from CLI options."""
    loader = PatternLoader()

    if interactive:
        return _interactive_select_patterns(loader)
    elif patterns:
        category_list = [c.strip() for c in patterns.split(",")]
        all_patterns = []
        for cat in category_list:
            all_patterns.extend(loader.load_category(cat))
        return [p.to_dict() for p in all_patterns]
    elif pattern_file:
        loaded = loader.load_custom(pattern_file)
        return [p.to_dict() for p in loaded]
    else:
        return [p.to_dict() for p in loader.load_all()]


def _interactive_select_patterns(loader: PatternLoader) -> list[dict]:
    """Interactive pattern selection menu."""
    all_patterns = loader.load_all()

    # Group by category
    categories: dict[str, list] = {}
    for p in all_patterns:
        categories.setdefault(p.category, []).append(p)

    console.print()
    console.print("[bold]Interactive Pattern Selection[/]")
    console.print("-" * 50)

    # Show categories
    cat_list = sorted(categories.keys())
    for i, cat in enumerate(cat_list, 1):
        count = len(categories[cat])
        console.print(f"  [cyan]{i}.[/] {cat} ({count} patterns)")

    console.print()
    console.print(
        "  [green]a.[/] All patterns "
        f"({len(all_patterns)} total)"
    )
    console.print("  [yellow]q.[/] Quit")
    console.print()

    # Get user selection
    from rich.prompt import Prompt

    choice = Prompt.ask(
        "Select categories (comma-separated numbers, 'a' for all, 'q' to quit)",
        default="a",
    )

    if choice.lower() == "q":
        console.print("[yellow]Aborted.[/]")
        raise typer.Exit(0)

    if choice.lower() == "a":
        return [p.to_dict() for p in all_patterns]

    # Parse selection
    selected_cats = []
    for part in choice.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(cat_list):
                selected_cats.append(cat_list[idx])

    if not selected_cats:
        console.print("[red]Invalid selection![/]")
        raise typer.Exit(1)

    # Show selected categories with patterns
    selected_patterns = []
    for cat in selected_cats:
        console.print(f"\n[bold]{cat}:[/]")
        for p in categories[cat]:
            if p.severity >= 8:
                sev_color = "red"
            elif p.severity >= 5:
                sev_color = "yellow"
            else:
                sev_color = "green"
            console.print(
                f"  [{sev_color}]{p.severity}[/] {p.name} "
                f"[dim]({p.id})[/]"
            )
            selected_patterns.append(p.to_dict())

    console.print(f"\n[bold]Selected {len(selected_patterns)} patterns[/]")

    # Ask to confirm or filter further
    confirm = Prompt.ask(
        "Start scan? [y/n/filter]",
        default="y",
    )

    if confirm.lower() == "n":
        console.print("[yellow]Aborted.[/]")
        raise typer.Exit(0)

    if confirm.lower() == "filter":
        # Filter by severity
        min_severity = Prompt.ask(
            "Minimum severity (1-10)",
            default="1",
        )
        try:
            min_sev = int(min_severity)
            selected_patterns = [
                p for p in selected_patterns if p.get("severity", 5) >= min_sev
            ]
            console.print(
                f"[dim]Filtered to {len(selected_patterns)} patterns "
                f"(severity >= {min_sev})[/]"
            )
        except ValueError:
            pass

    return selected_patterns


async def _run_single_turn(
    scanner_instance: Scanner,
    pattern_dicts: list[dict],
    progress: Progress,
    task_id: int,
) -> ScanSummary:
    """Run single-turn scan with progress bar."""
    import time

    from scanner.core.scanner import ScanSummary as Summary

    summary = Summary(
        model=scanner_instance.config.model,
        total_patterns=len(pattern_dicts),
    )

    start_time = time.monotonic()
    semaphore = asyncio.Semaphore(scanner_instance.config.concurrency)

    async def bounded_scan(pattern: dict) -> ScanResult:
        async with semaphore:
            result = await scanner_instance.scan_pattern(pattern)
            progress.advance(task_id)
            return result

    tasks = [bounded_scan(p) for p in pattern_dicts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            summary.errors += 1
        elif isinstance(r, ScanResult):
            summary.results.append(r)
            summary.scanned += 1
            if r.classification == "COMPROMISED":
                summary.vulnerable += 1
            elif r.classification == "REFUSED":
                summary.refused += 1
            elif r.classification == "PARTIAL":
                summary.partial += 1
            elif r.classification == "ERROR":
                summary.errors += 1

    summary.duration_seconds = time.monotonic() - start_time
    return summary


async def _run_multi_turn(
    scanner_instance: Scanner,
    pattern_dicts: list[dict],
    strategy: str,
    max_turns: int,
    progress: Progress,
    task_id: int,
) -> ScanSummary:
    """Run multi-turn scan with progress bar."""
    import time

    from scanner.core.multi_turn import AttackStrategy, MultiTurnEngine
    from scanner.core.scanner import ScanSummary as Summary

    engine = MultiTurnEngine(
        provider=scanner_instance.target_provider,
        max_turns=max_turns,
    )
    strategy_enum = AttackStrategy(strategy)

    summary = Summary(
        model=scanner_instance.config.model,
        total_patterns=len(pattern_dicts),
    )

    start_time = time.monotonic()
    for p in pattern_dicts:
        mt_result = await engine.attack(
            initial_prompt=p.get("payload", ""),
            strategy=strategy_enum,
            pattern_id=p.get("id", "unknown"),
        )

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

        summary.results.append(scan_result)
        summary.scanned += 1
        if scan_result.classification == "COMPROMISED":
            summary.vulnerable += 1
        elif scan_result.classification == "REFUSED":
            summary.refused += 1
        elif scan_result.classification == "PARTIAL":
            summary.partial += 1

        progress.advance(task_id)

    summary.duration_seconds = time.monotonic() - start_time
    return summary


def _generate_reports(
    summary: ScanSummary,
    output: str,
    output_dir: str,
    model: str,
) -> None:
    """Generate reports for a scan summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Use model name in filename for batch mode
    model_safe = model.replace("/", "_").replace(":", "_")

    if "json" in output:
        json_path = output_path / f"{model_safe}_results.json"
        generate_json_report(summary, json_path)
        console.print(f"[dim]JSON report: {json_path}[/]")

    if "markdown" in output or "md" in output:
        md_path = output_path / f"{model_safe}_report.md"
        generate_markdown_report(summary, md_path)
        console.print(f"[dim]Markdown report: {md_path}[/]")

    if "sarif" in output:
        sarif_path = output_path / f"{model_safe}_results.sarif"
        generate_sarif_report(summary, sarif_path)
        console.print(f"[dim]SARIF report: {sarif_path}[/]")


@app.command()
def scan(
    model: str = typer.Option(
        ..., "--model", "-m",
        help="Target model (e.g., qwen2.5:3b, nvidia/nemotron-3-ultra-550b-a55b:free)"
    ),
    patterns: str | None = typer.Option(
        None, "--patterns", "-p", help="Comma-separated pattern categories"
    ),
    pattern_file: str | None = typer.Option(
        None, "--pattern-file", help="Custom pattern JSON file or directory"
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
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive pattern selection"
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
    # Load patterns
    pattern_dicts = _load_patterns(patterns, pattern_file, interactive)

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

    scanner_instance = Scanner(
        config=config,
        judge_provider=judge_provider,
    )

    # Run scan with progress bar
    print_scan_header(model, len(pattern_dicts))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        console=console,
    ) as progress:
        task_id = progress.add_task("Scanning...", total=len(pattern_dicts))

        async def run() -> ScanSummary:
            if multi_turn:
                return await _run_multi_turn(
                    scanner_instance, pattern_dicts, strategy, max_turns,
                    progress, task_id,
                )
            else:
                if streaming:
                    console.print("[dim]Streaming mode (collect-then-judge)[/]")
                return await _run_single_turn(
                    scanner_instance, pattern_dicts, progress, task_id,
                )

        summary = asyncio.run(run())

    # Print summary
    print_scan_summary(summary)

    # Save to history
    _save_to_history(summary)

    # Generate reports
    _generate_reports(summary, output, output_dir, model)


@app.command(name="batch-scan")
def batch_scan(
    models: str = typer.Option(
        ..., "--models", help="Comma-separated list of models to scan"
    ),
    patterns: str | None = typer.Option(
        None, "--patterns", "-p", help="Comma-separated pattern categories"
    ),
    pattern_file: str | None = typer.Option(
        None, "--pattern-file", help="Custom pattern JSON file or directory"
    ),
    judge_model: str | None = typer.Option(
        None, "--judge-model", "-j", help="Judge model"
    ),
    multi_turn: bool = typer.Option(
        False, "--multi-turn", help="Enable multi-turn testing"
    ),
    strategy: str = typer.Option(
        "crescendo", "--strategy", "-s",
        help="Multi-turn strategy"
    ),
    max_turns: int = typer.Option(
        5, "--max-turns", help="Max turns for multi-turn testing"
    ),
    output: str = typer.Option(
        "console", "--output", "-o", help="Output formats"
    ),
    output_dir: str = typer.Option(
        "./reports", "--output-dir", help="Output directory"
    ),
    concurrency: int = typer.Option(
        3, "--concurrency", "-c", help="Max parallel requests"
    ),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Request timeout"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging"
    ),
) -> None:
    """Scan multiple models and compare results."""
    model_list = [m.strip() for m in models.split(",") if m.strip()]

    if not model_list:
        console.print("[red]No models specified![/]")
        raise typer.Exit(1)

    # Load patterns
    pattern_dicts = _load_patterns(patterns, pattern_file)

    if not pattern_dicts:
        console.print("[red]No patterns found![/]")
        raise typer.Exit(1)

    console.print(
        f"[bold]Batch scan: {len(model_list)} models, "
        f"{len(pattern_dicts)} patterns[/]"
    )
    console.print()

    summaries: list[ScanSummary] = []

    for i, model in enumerate(model_list, 1):
        console.print(f"[bold blue]{'='*60}[/]")
        console.print(
            f"[bold]Model {i}/{len(model_list)}:[/] {model}"
        )
        console.print(f"[bold blue]{'='*60}[/]")

        # Create config for this model
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

        scanner_instance = Scanner(
            config=config,
            judge_provider=judge_provider,
        )

        # Run scan with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                f"[{model}] Scanning...", total=len(pattern_dicts)
            )

            # Bind loop variables for closure
            _scanner = scanner_instance
            _patterns = pattern_dicts
            _task = task_id

            async def run(
                _s: Scanner = _scanner,
                _p: list[dict] = _patterns,
                _t: int = _task,
            ) -> ScanSummary:
                if multi_turn:
                    return await _run_multi_turn(
                        _s, _p, strategy, max_turns,
                        progress, _t,
                    )
                else:
                    return await _run_single_turn(
                        _s, _p, progress, _t,
                    )

            summary = asyncio.run(run())

        print_scan_summary(summary)
        _save_to_history(summary)
        _generate_reports(summary, output, output_dir, model)
        summaries.append(summary)

    # Print comparison table
    if len(summaries) > 1:
        console.print()
        console.print("[bold]📊 Model Comparison[/]")
        console.print("-" * 70)

        from rich.table import Table

        table = Table(title="Security Comparison")
        table.add_column("Model", style="bold", max_width=35)
        table.add_column("REFUSED", justify="right", style="green")
        table.add_column("PARTIAL", justify="right", style="yellow")
        table.add_column("COMPROMISED", justify="right", style="red")
        table.add_column("Risk Level", justify="center")
        table.add_column("Duration", justify="right")

        for s in summaries:
            total = s.scanned if s.scanned > 0 else 1
            table.add_row(
                s.model[:35],
                f"{s.refused/total*100:.0f}%",
                f"{s.partial/total*100:.0f}%",
                f"{s.vulnerable/total*100:.0f}%",
                s.risk_level,
                f"{s.duration_seconds:.1f}s",
            )

        console.print(table)


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


@app.command(name="validate-patterns")
def validate_patterns(
    pattern_path: str = typer.Argument(
        ..., help="Path to pattern file or directory to validate"
    ),
) -> None:
    """Validate custom pattern files."""
    from scanner.patterns.loader import PatternLoader

    loader = PatternLoader()

    try:
        patterns = loader.load_custom(pattern_path)
    except Exception as e:
        console.print(f"[red]Error loading patterns: {e}[/]")
        raise typer.Exit(1) from e

    if not patterns:
        console.print("[yellow]No patterns found[/]")
        raise typer.Exit(1)

    valid_count = 0
    invalid_count = 0

    for pattern in patterns:
        is_valid, error = PatternLoader.validate_pattern(pattern.to_dict())
        if is_valid:
            valid_count += 1
            console.print(f"[green]✓ {pattern.id}[/]")
        else:
            invalid_count += 1
            console.print(f"[red]✗ {pattern.id}: {error}[/]")

    console.print(f"\n[bold]Results: {valid_count} valid, {invalid_count} invalid[/]")

    if invalid_count > 0:
        raise typer.Exit(1)


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


@app.command(name="history")
def history(
    model: str | None = typer.Option(
        None, "--model", "-m", help="Filter by model name"
    ),
    limit: int = typer.Option(
        20, "--limit", "-l", help="Number of entries to show"
    ),
    stats: bool = typer.Option(
        False, "--stats", "-s", help="Show model statistics"
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Clear all history"
    ),
) -> None:
    """View scan history."""
    from scanner.core.history import HistoryManager

    manager = HistoryManager()

    if clear:
        count = manager.clear()
        console.print(f"[green]Cleared {count} history entries[/]")
        return

    if stats:
        if not model:
            console.print("[red]--model required for stats[/]")
            raise typer.Exit(1)

        model_stats = manager.get_model_stats(model)
        if model_stats["total_scans"] == 0:
            console.print(f"[yellow]No scans found for '{model}'[/]")
            return

        console.print(f"\n[bold]Statistics for: {model}[/]")
        console.print("-" * 40)
        console.print(f"Total scans: {model_stats['total_scans']}")
        console.print(
            f"Avg REFUSED: {model_stats['avg_refused_pct']:.1f}%"
        )
        console.print(
            f"Avg COMPROMISED: {model_stats['avg_compromised_pct']:.1f}%"
        )
        console.print(
            f"Avg duration: {model_stats['avg_duration']:.1f}s"
        )
        console.print(f"Last scan: {model_stats['last_scan']}")
        return

    entries = manager.get_entries(model=model, limit=limit)

    if not entries:
        console.print("[yellow]No scan history found[/]")
        return

    from rich.table import Table

    table = Table(title=f"Scan History ({len(entries)} entries)")
    table.add_column("Time", style="dim")
    table.add_column("Model", max_width=35)
    table.add_column("REFUSED", justify="right", style="green")
    table.add_column("PARTIAL", justify="right", style="yellow")
    table.add_column("COMPROMISED", justify="right", style="red")
    table.add_column("Risk", justify="center")
    table.add_column("Duration", justify="right")

    for e in entries:
        total = e.scanned if e.scanned > 0 else 1
        risk_color = {
            "CRITICAL": "red",
            "HIGH": "red",
            "MEDIUM": "yellow",
            "LOW": "green",
        }.get(e.risk_level, "white")

        # Format timestamp
        try:
            dt = datetime.fromisoformat(e.timestamp)
            time_str = dt.strftime("%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = e.timestamp[:16]

        table.add_row(
            time_str,
            e.model[:35],
            f"{e.refused/total*100:.0f}%",
            f"{e.partial/total*100:.0f}%",
            f"{e.vulnerable/total*100:.0f}%",
            f"[{risk_color}]{e.risk_level}[/]",
            f"{e.duration_seconds:.1f}s",
        )

    console.print(table)


def _save_to_history(summary: ScanSummary) -> None:
    """Save scan summary to history."""
    from scanner.core.history import HistoryManager, ScanHistoryEntry

    manager = HistoryManager()
    entry = ScanHistoryEntry(
        timestamp=datetime.now(UTC).isoformat(),
        model=summary.model,
        total_patterns=summary.total_patterns,
        scanned=summary.scanned,
        vulnerable=summary.vulnerable,
        refused=summary.refused,
        partial=summary.partial,
        errors=summary.errors,
        risk_level=summary.risk_level,
        duration_seconds=summary.duration_seconds,
    )
    manager.add_entry(entry)


if __name__ == "__main__":
    app()
