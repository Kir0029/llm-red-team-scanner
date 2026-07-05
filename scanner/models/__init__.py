"""LLM model providers for LLM Red Team Scanner."""

import os

from scanner.models.anthropic_provider import AnthropicProvider
from scanner.models.base import Message, ModelProvider, ModelResponse, ProviderType
from scanner.models.ollama_provider import OllamaProvider
from scanner.models.openai_provider import OpenAIProvider

__all__ = [
    "Message",
    "ModelProvider",
    "ModelResponse",
    "ProviderType",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "create_provider",
]


def create_provider(
    model: str,
    provider_type: str | None = None,
    **kwargs: object,
) -> ModelProvider:
    """Factory function to create a model provider.

    Args:
        model: Model name (e.g., 'qwen2.5:3b', 'gpt-4', 'claude-3-opus')
               For OpenRouter: 'openrouter/google/gemini-2.0-flash-001'
        provider_type: Force provider type ('ollama', 'openai', 'anthropic')
                      If None, auto-detect from model name
        **kwargs: Additional provider-specific arguments

    Returns:
        ModelProvider instance

    Raises:
        ValueError: If provider type cannot be determined
    """
    if provider_type:
        pt = provider_type.lower()
    else:
        # Auto-detect from model name
        if model.startswith("openrouter/"):
            pt = "openrouter"
        elif model.startswith("gpt-") or model.startswith("o1-"):
            pt = "openai"
        elif model.startswith("claude-"):
            pt = "anthropic"
        elif "/" in model:
            # Any other model with / (e.g. nvidia/nemotron, google/gemma)
            # is likely an OpenRouter model
            pt = "openrouter"
        else:
            pt = "ollama"

    if pt == "ollama":
        return OllamaProvider(model=model, **kwargs)  # type: ignore[arg-type]
    elif pt == "openai":
        return OpenAIProvider(model=model, **kwargs)  # type: ignore[arg-type]
    elif pt == "anthropic":
        return AnthropicProvider(model=model, **kwargs)  # type: ignore[arg-type]
    elif pt == "openrouter":
        # OpenRouter uses OpenAI-compatible API
        openrouter_model = model.replace("openrouter/", "")
        api_key = kwargs.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        base_url = "https://openrouter.ai/api/v1"
        return OpenAIProvider(
            model=openrouter_model,
            api_key=api_key,
            base_url=base_url,
        )
    else:
        raise ValueError(f"Unknown provider type: {pt}")
