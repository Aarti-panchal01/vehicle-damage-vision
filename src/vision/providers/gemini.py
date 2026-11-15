"""Gemini provider using the official google-genai SDK."""

from __future__ import annotations

import os

from src.vision.providers.base import ContentPart, ImageInput, ProviderReply, VisionProvider

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


class GeminiProvider(VisionProvider):
    """Calls a Gemini model through google-genai. Reads GEMINI_API_KEY from the environment."""

    name = "gemini"

    def __init__(
        self,
        model: str = DEFAULT_GEMINI_MODEL,
        api_key: str | None = None,
        thinking_level: str | None = "low",
        min_interval_s: float = 4.0,
    ):
        super().__init__(model=model, min_interval_s=min_interval_s)
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        self.client = genai.Client(api_key=key)
        self.thinking_level = thinking_level

    def _generate(self, parts: list[ContentPart], json_schema: dict | None) -> ProviderReply:
        from google.genai import types

        contents = [
            types.Part.from_bytes(data=part.data, mime_type=part.mime_type) if isinstance(part, ImageInput) else part
            for part in parts
        ]
        config_args: dict = {}
        if self.thinking_level:
            config_args["thinking_config"] = types.ThinkingConfig(thinking_level=self.thinking_level)
        if json_schema is not None:
            config_args["response_mime_type"] = "application/json"
            config_args["response_json_schema"] = json_schema
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(**config_args),
        )
        usage = response.usage_metadata
        return ProviderReply(
            text=response.text or "",
            model=self.model,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            thinking_tokens=(usage.thoughts_token_count or 0) if usage else 0,
        )
