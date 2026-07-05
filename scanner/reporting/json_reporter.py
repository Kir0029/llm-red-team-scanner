"""JSON reporter for scan results."""

import json
from datetime import UTC, datetime
from pathlib import Path

from scanner.core.scanner import ScanResult, ScanSummary


def generate_json_report(
    summary: ScanSummary,
    output_path: str | Path | None = None,
) -> str:
    """Generate JSON report from scan summary.

    Args:
        summary: Scan summary with all results
        output_path: Optional path to write JSON file

    Returns:
        JSON string of the report
    """
    report = {
        "metadata": {
            "tool": "llm-red-team-scanner",
            "version": "0.1.0",
            "timestamp": datetime.now(UTC).isoformat(),
            "target_model": summary.model,
        },
        "summary": {
            "total_patterns": summary.total_patterns,
            "scanned": summary.scanned,
            "vulnerable": summary.vulnerable,
            "refused": summary.refused,
            "partial": summary.partial,
            "errors": summary.errors,
            "duration_seconds": round(summary.duration_seconds, 2),
            "overall_risk": summary.risk_level,
        },
        "results": [_result_to_dict(r) for r in summary.results],
    }

    json_str = json.dumps(report, indent=2, ensure_ascii=False)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str, encoding="utf-8")

    return json_str


def _result_to_dict(result: ScanResult) -> dict:
    """Convert ScanResult to dictionary."""
    return {
        "pattern_id": result.pattern_id,
        "pattern_name": result.pattern_name,
        "category": result.category,
        "severity": result.severity,
        "payload": result.payload,
        "response": result.response,
        "classification": result.classification,
        "confidence": round(result.confidence, 3),
        "risk_score": round(result.risk_score, 2),
        "success": result.success,
        "error": result.error,
        "duration_ms": round(result.duration_ms, 1),
    }
