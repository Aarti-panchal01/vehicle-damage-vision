"""Groq provider for the open-weight VLM comparison (Qwen 3.8 27B by default)."""

from __future__ import annotations

import base64
import os

from src.vision.providers.base import ContentPart, ImageInput, ProviderReply, VisionProvider

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
GROQ_MAX_IMAGES_PER_REQUEST = 3


class GroqProvider(VisionProvider):
    """Calls a Groq-hosted vision model. Reads GROQ_API_KEY from the environment.

    Groq accepts at most 3 images per request, which is why few-shot prompts in
    this project use 2 example photos plus the photo being assessed.
    """

    name = "groq"

    def __init__(self, model: str = DEFAULT_GROQ_MODEL, api_key: str | None = None, min_interval_s: float = 2.5):
        super().__init__(model=model, min_interval_s=min_interval_s, max_attempts=10)
        from groq import Groq

        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")
        self.client = Groq(api_key=key)

    def _generate(self, parts: list[ContentPart], json_schema: dict | None) -> ProviderReply:
        image_count = sum(isinstance(part, ImageInput) for part in parts)
        if image_count > GROQ_MAX_IMAGES_PER_REQUEST:
            raise ValueError(f"Groq accepts at most {GROQ_MAX_IMAGES_PER_REQUEST} images, got {image_count}")
        content = [to_groq_content(part) for part in parts]
        request: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "reasoning_format": "hidden",
        }
        if json_schema is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "vision_output", "strict": True, "schema": json_schema},
            }
        response = self.client.chat.completions.create(**request)
        usage = response.usage
        return ProviderReply(
            text=response.choices[0].message.content or "",
            model=self.model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


def to_groq_content(part: ContentPart) -> dict:
    """Convert one text or image part into the OpenAI-style content block Groq expects."""
    if isinstance(part, ImageInput):
        encoded = base64.b64encode(part.data).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{part.mime_type};base64,{encoded}"}}
    return {"type": "text", "text": part}
