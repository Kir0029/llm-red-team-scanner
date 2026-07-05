"""Input validators for LLM Red Team Scanner."""

import re
from pathlib import Path

from scanner.core.exceptions import PatternError


def validate_model_name(model: str) -> str:
    """Validate model name format.

    Args:
        model: Model name to validate

    Returns:
        Validated model name

    Raises:
        ValueError: If model name is invalid
    """
    if not model or not model.strip():
        raise ValueError("Model name cannot be empty")

    model = model.strip()

    # Allow provider/model format (e.g., openai/gpt-4, ollama/llama3)
    if not re.match(r"^[a-zA-Z0-9_\-.:/]+$", model):
        raise ValueError(f"Invalid model name: {model}")

    return model


def validate_pattern_file(file_path: str) -> Path:
    """Validate pattern file exists and is readable.

    Args:
        file_path: Path to pattern file

    Returns:
        Validated Path object

    Raises:
        PatternError: If file doesn't exist or is invalid
    """
    path = Path(file_path)

    if not path.exists():
        raise PatternError(f"Pattern file not found: {file_path}")

    if not path.is_file():
        raise PatternError(f"Pattern path is not a file: {file_path}")

    if path.suffix.lower() != ".json":
        raise PatternError(f"Pattern file must be JSON: {file_path}")

    return path


def validate_output_dir(dir_path: str) -> Path:
    """Validate and create output directory.

    Args:
        dir_path: Path to output directory

    Returns:
        Validated Path object
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_concurrency(concurrency: int) -> int:
    """Validate concurrency value.

    Args:
        concurrency: Number of concurrent requests

    Returns:
        Validated concurrency value

    Raises:
        ValueError: If concurrency is out of range
    """
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1")
    if concurrency > 20:
        raise ValueError("Concurrency cannot exceed 20")
    return concurrency
