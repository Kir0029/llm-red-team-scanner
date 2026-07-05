"""Logging setup for LLM Red Team Scanner."""

import logging
import sys


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the scanner.

    Args:
        verbose: Enable debug logging

    Returns:
        Configured logger instance
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt=date_format,
        stream=sys.stderr,
        force=True,
    )

    logger = logging.getLogger("scanner")

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    return logger
