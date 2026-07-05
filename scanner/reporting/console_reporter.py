"""Console reporter with Rich tables and progress bars."""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from scanner.core.scanner import ScanResult, ScanSummary
from scanner.scoring.calculator import get_risk_emoji

# Use emojis only if terminal supports UTF-8
USE_EMOJI = sys.stdout.encoding and sys.stdout.encoding.lower() in ("utf-8", "utf8")

console = Console()


def print_scan_header(model: str, total_patterns: int) -> None:
    """Print scan header with model info."""
    title = "[ LLM Red Team Scanner ]" if not USE_EMOJI else "🔍 LLM Red Team Scanner"
    console.print()
    console.print(
        Panel(
            f"[bold]Scanning:[/] {model}\n"
            f"[bold]Patterns:[/] {total_patterns}",
            title=title,
            border_style="blue",
        )
    )


def print_scan_result(result: ScanResult, current: int, total: int) -> None:
    """Print single scan result."""
    status = result.classification
    if status == "COMPROMISED":
        status_text = f"[red]{status}[/]"
    elif status == "REFUSED":
        status_text = f"[green]{status}[/]"
    elif status == "PARTIAL":
        status_text = f"[yellow]{status}[/]"
    else:
        status_text = f"[dim]{status}[/]"

    console.print(
        f"  {current}/{total} {result.pattern_name[:40]:<40} "
        f"{status_text}  "
        f"{result.risk_score:.1f}/10"
    )


def print_scan_summary(summary: ScanSummary) -> None:
    """Print scan summary with statistics."""
    console.print()
    summary_label = "[ Scan Summary ]" if not USE_EMOJI else "[bold]📊 Scan Summary[/]"
    console.print(summary_label)
    console.print("-" * 50)

    # Overall risk level
    risk_level = summary.risk_level
    emoji = get_risk_emoji(risk_level) if USE_EMOJI else ""
    console.print(f"Overall Risk: {emoji} [bold]{risk_level}[/]")
    console.print(f"Duration: {summary.duration_seconds:.1f}s")
    console.print()

    # Statistics table
    table = Table(title="Results by Classification")
    table.add_column("Classification", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    total = summary.scanned if summary.scanned > 0 else 1
    table.add_row(
        "[red]COMPROMISED[/]",
        str(summary.vulnerable),
        f"{summary.vulnerable/total*100:.1f}%",
    )
    table.add_row(
        "[green]REFUSED[/]",
        str(summary.refused),
        f"{summary.refused/total*100:.1f}%",
    )
    table.add_row(
        "[yellow]PARTIAL[/]",
        str(summary.partial),
        f"{summary.partial/total*100:.1f}%",
    )
    table.add_row(
        "[dim]ERRORS[/]",
        str(summary.errors),
        f"{summary.errors/total*100:.1f}%",
    )

    console.print(table)
    console.print()

    # Risk breakdown
    risk_table = Table(title="Risk Score Distribution")
    risk_table.add_column("Level", style="bold")
    risk_table.add_column("Count", justify="right")

    critical = sum(
        1 for r in summary.results if r.risk_score >= 9.0
    )
    high = sum(
        1 for r in summary.results if 7.0 <= r.risk_score < 9.0
    )
    medium = sum(
        1 for r in summary.results if 4.0 <= r.risk_score < 7.0
    )
    low = sum(1 for r in summary.results if r.risk_score < 4.0)

    risk_table.add_row("[red]Critical (9-10)[/]", str(critical))
    risk_table.add_row("[orange]High (7-8.9)[/]", str(high))
    risk_table.add_row("[yellow]Medium (4-6.9)[/]", str(medium))
    risk_table.add_row("[green]Low (0-3.9)[/]", str(low))

    console.print(risk_table)

    # Detailed results
    if summary.results:
        console.print()
        if USE_EMOJI:
            console.print("[bold]📋 Detailed Results[/]")
        else:
            console.print("[ Detailed Results ]")
        console.print("-" * 50)

        detail_table = Table(show_header=True)
        detail_table.add_column("Pattern", max_width=35)
        detail_table.add_column("Category", max_width=15)
        detail_table.add_column("Status", max_width=12)
        detail_table.add_column("Score", justify="right", width=8)

        for r in sorted(
            summary.results, key=lambda x: x.risk_score, reverse=True
        ):
            status_color = {
                "COMPROMISED": "red",
                "REFUSED": "green",
                "PARTIAL": "yellow",
                "ERROR": "dim",
            }.get(r.classification, "white")

            detail_table.add_row(
                r.pattern_name[:35],
                r.category,
                f"[{status_color}]{r.classification}[/]",
                f"{r.risk_score:.1f}",
            )

        console.print(detail_table)
