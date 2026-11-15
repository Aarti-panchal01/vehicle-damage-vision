"""Offline provider for unit tests, CI and UI work without an API key."""

from __future__ import annotations

from src.vision.providers.base import ContentPart, ProviderReply, VisionProvider


class MockProvider(VisionProvider):
    """Returns scripted replies in order, and records every request it receives."""

    name = "mock"

    def __init__(self, replies: list[str], model: str = "mock-vlm"):
        super().__init__(model=model, min_interval_s=0.0, max_attempts=1)
        self.replies = list(replies)
        self.requests: list[tuple[list[ContentPart], dict | None]] = []

    def _generate(self, parts: list[ContentPart], json_schema: dict | None) -> ProviderReply:
        self.requests.append((parts, json_schema))
        if not self.replies:
            raise RuntimeError("MockProvider ran out of scripted replies")
        text = self.replies.pop(0)
        return ProviderReply(text=text, model=self.model, input_tokens=100, output_tokens=len(text) // 4)
