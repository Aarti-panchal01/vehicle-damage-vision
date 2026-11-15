"""Disk cache that wraps any provider so repeated evaluation runs cost nothing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.vision.providers.base import ContentPart, ImageInput, ProviderReply, VisionProvider


class CachedProvider(VisionProvider):
    """Stores each reply as JSON keyed by a hash of provider, model, request parts and schema."""

    def __init__(self, inner: VisionProvider, cache_dir: Path):
        super().__init__(model=inner.model, min_interval_s=0.0, max_attempts=1)
        self.inner = inner
        self.name = inner.name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def request_key(self, parts: list[ContentPart], json_schema: dict | None) -> str:
        """Hash every input that can change the reply."""
        digest = hashlib.sha256()
        digest.update(f"{self.inner.name}|{self.inner.model}|".encode())
        digest.update(json.dumps(getattr(self.inner, "thinking_level", None)).encode())
        for part in parts:
            if isinstance(part, ImageInput):
                digest.update(b"IMG" + hashlib.sha256(part.data).digest())
            else:
                digest.update(b"TXT" + part.encode("utf-8"))
        digest.update(json.dumps(json_schema, sort_keys=True).encode())
        return digest.hexdigest()[:32]

    def generate(self, parts: list[ContentPart], json_schema: dict | None = None) -> ProviderReply:
        path = self.cache_dir / f"{self.request_key(parts, json_schema)}.json"
        if path.exists():
            reply = ProviderReply.from_dict(json.loads(path.read_text(encoding="utf-8")))
            reply.from_cache = True
            return reply
        reply = self.inner.generate(parts, json_schema)
        path.write_text(json.dumps(reply.to_dict(), indent=1), encoding="utf-8")
        return reply

    def _generate(self, parts: list[ContentPart], json_schema: dict | None) -> ProviderReply:
        return self.generate(parts, json_schema)
