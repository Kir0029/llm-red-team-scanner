"""Custom exceptions for LLM Red Team Scanner."""


class ScannerError(Exception):
    """Base exception for scanner errors."""


class ProviderError(ScannerError):
    """Error communicating with LLM provider."""


class PatternError(ScannerError):
    """Error loading or validating patterns."""


class ScoringError(ScannerError):
    """Error calculating risk scores."""


class ReportError(ScannerError):
    """Error generating reports."""


class RateLimitError(ProviderError):
    """Rate limit exceeded."""


class TimeoutError(ProviderError):
    """Request timed out."""


class AuthenticationError(ProviderError):
    """Authentication failed."""


class ModelNotFoundError(ProviderError):
    """Model not found or not available."""
