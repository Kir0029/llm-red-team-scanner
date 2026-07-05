"""SARIF reporter for scan results (industry standard)."""

import json
from pathlib import Path

from scanner.core.scanner import ScanResult, ScanSummary


def generate_sarif_report(
    summary: ScanSummary,
    output_path: str | Path | None = None,
) -> str:
    """Generate SARIF 2.1.0 report from scan summary.

    SARIF (Static Analysis Results Interchange Format) is the
    industry standard for security findings. Supported by GitHub,
    Azure DevOps, and VS Code.

    Args:
        summary: Scan summary with all results
        output_path: Optional path to write SARIF file

    Returns:
        SARIF JSON string
    """
    # Build rules from unique pattern IDs
    rules = {}
    for result in summary.results:
        if result.pattern_id not in rules:
            rules[result.pattern_id] = {
                "id": result.pattern_id,
                "name": result.pattern_name,
                "shortDescription": {
                    "text": f"LLM security test: {result.pattern_name}"
                },
                "fullDescription": {
                    "text": f"Test for {result.category} vulnerability"
                },
                "helpUri": "https://owasp.org/www-project-top-10-for-large-language-model-applications/",
                "properties": {
                    "category": result.category,
                    "severity": result.severity,
                },
            }

    # Build results
    sarif_results = []
    for result in summary.results:
        level = _classification_to_level(result.classification)

        sarif_result = {
            "ruleId": result.pattern_id,
            "level": level,
            "message": {
                "text": _build_message(result),
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f"model:{summary.model}",
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": 1,
                        },
                    }
                }
            ],
            "properties": {
                "classification": result.classification,
                "confidence": result.confidence,
                "risk_score": result.risk_score,
                "category": result.category,
            },
        }

        if result.error:
            sarif_result["properties"]["error"] = result.error

        sarif_results.append(sarif_result)

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "llm-red-team-scanner",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/Kir0029/llm-red-team-scanner",
                        "rules": list(rules.values()),
                    }
                },
                "results": sarif_results,
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "properties": {
                            "target_model": summary.model,
                            "patterns_tested": summary.scanned,
                            "duration_seconds": summary.duration_seconds,
                        },
                    }
                ],
            }
        ],
    }

    json_str = json.dumps(sarif, indent=2, ensure_ascii=False)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str, encoding="utf-8")

    return json_str


def _classification_to_level(classification: str) -> str:
    """Map classification to SARIF level."""
    mapping = {
        "COMPROMISED": "error",
        "PARTIAL": "warning",
        "REFUSED": "note",
        "ERROR": "none",
    }
    return mapping.get(classification, "none")


def _build_message(result: ScanResult) -> str:
    """Build human-readable message."""
    if result.classification == "COMPROMISED":
        return (
            f"Model is vulnerable to {result.pattern_name}. "
            f"Classification: COMPROMISED "
            f"(confidence: {result.confidence:.1%}). "
            f"Risk score: {result.risk_score:.1f}/10."
        )
    elif result.classification == "REFUSED":
        return (
            f"Model safely refused {result.pattern_name}. "
            f"Classification: REFUSED "
            f"(confidence: {result.confidence:.1%})."
        )
    elif result.classification == "PARTIAL":
        return (
            f"Model partially complied with {result.pattern_name}. "
            f"Classification: PARTIAL "
            f"(confidence: {result.confidence:.1%}). "
            f"Risk score: {result.risk_score:.1f}/10."
        )
    else:
        return (
            f"Error testing {result.pattern_name}: {result.error}"
        )
