"""VLM providers and a factory that builds one by name."""

from __future__ import annotations

from src.vision.providers.base import (
    ImageInput,
    ProviderError,
    ProviderReply,
    QuotaExhaustedError,
    VisionProvider,
)
from src.vision.providers.mock import MockProvider


def make_provider(name: str, model: str | None = None) -> VisionProvider:
    """Build a provider by name: "gemini" or "groq". The SDK is imported only when needed."""
    if name == "gemini":
        from src.vision.providers.gemini import DEFAULT_GEMINI_MODEL, GeminiProvider

        return GeminiProvider(model=model or DEFAULT_GEMINI_MODEL)
    if name == "groq":
        from src.vision.providers.groq import DEFAULT_GROQ_MODEL, GroqProvider

        return GroqProvider(model=model or DEFAULT_GROQ_MODEL)
    raise ValueError(f"Unknown provider {name!r}; expected 'gemini' or 'groq'")


__all__ = [
    "ImageInput",
    "MockProvider",
    "ProviderError",
    "ProviderReply",
    "QuotaExhaustedError",
    "VisionProvider",
    "make_provider",
]
