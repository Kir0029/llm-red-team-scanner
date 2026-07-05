"""Configuration management for LLM Red Team Scanner."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class OutputFormat(StrEnum):
    """Output format options."""

    CONSOLE = "console"
    JSON = "json"
    MARKDOWN = "markdown"
    SARIF = "sarif"


class ScanConfig(BaseModel):
    """Configuration for a scan operation."""

    model: str = Field(..., description="Target model identifier")
    patterns: list[str] = Field(
        default_factory=list, description="Pattern categories to test"
    )
    pattern_file: str | None = Field(None, description="Custom pattern file path")
    judge_model: str | None = Field(None, description="Judge model for LLM-as-judge")
    output_formats: list[OutputFormat] = Field(
        default_factory=lambda: [OutputFormat.CONSOLE],
        description="Output formats",
    )
    output_dir: Path = Field(default=Path("./reports"), description="Output directory")
    concurrency: int = Field(
        default=3, ge=1, le=20, description="Max parallel requests"
    )
    timeout: int = Field(
        default=30, ge=5, le=300, description="Request timeout in seconds"
    )
    verbose: bool = Field(default=False, description="Enable debug logging")

    model_config = {"use_enum_values": True}
