"""Provider abstraction so the VLM behind the vision module can be swapped."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Callable, TypeVar, Union

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class ImageInput:
    """One photo sent to the model."""

    data: bytes
    mime_type: str = "image/jpeg"


ContentPart = Union[str, ImageInput]


@dataclass
class ProviderReply:
    """Text returned by a provider plus the usage numbers the evaluation needs."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    latency_s: float = 0.0
    from_cache: bool = False
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProviderReply":
        return cls(**data)


class ProviderError(RuntimeError):
    """Raised when a provider call fails after all retries."""


class QuotaExhaustedError(ProviderError):
    """Raised when the provider reports a daily quota that waiting will not fix."""


class VisionProvider(ABC):
    """Base class for every VLM backend."""

    name: str = "base"

    def __init__(self, model: str, min_interval_s: float = 0.0, max_attempts: int = 5):
        self.model = model
        self.min_interval_s = min_interval_s
        self.max_attempts = max_attempts
        self._last_call_at = 0.0

    @abstractmethod
    def _generate(self, parts: list[ContentPart], json_schema: dict | None) -> ProviderReply:
        """Send one request. parts is an ordered mix of text and images."""

    def generate(self, parts: list[ContentPart], json_schema: dict | None = None) -> ProviderReply:
        """Send one request with rate spacing and retry on transient errors."""
        return self._with_backoff(lambda: self._timed(parts, json_schema))

    def _timed(self, parts: list[ContentPart], json_schema: dict | None) -> ProviderReply:
        wait = self.min_interval_s - (time.monotonic() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)
        started = time.monotonic()
        self._last_call_at = started
        reply = self._generate(parts, json_schema)
        reply.latency_s = round(time.monotonic() - started, 3)
        return reply

    def _with_backoff(self, call: Callable[[], ResultT]) -> ResultT:
        delay = 5.0
        for attempt in range(1, self.max_attempts + 1):
            try:
                return call()
            except Exception as error:
                status = status_code_of(error)
                message = str(error)
                if status == 429 and is_daily_quota_message(message):
                    raise QuotaExhaustedError(message) from error
                if status not in RETRIABLE_STATUS_CODES or attempt == self.max_attempts:
                    raise ProviderError(f"{self.name} call failed (status {status}): {message[:500]}") from error
                pause = retry_delay_from_message(message) or delay
                logger.warning("%s returned %s, retrying in %.0fs (attempt %d)", self.name, status, pause, attempt)
                time.sleep(pause)
                delay = min(delay * 2, 120.0)
        raise ProviderError(f"{self.name} call failed after {self.max_attempts} attempts")


def status_code_of(error: Exception) -> int | None:
    """Read an HTTP status code from SDK exceptions that expose one."""
    for attribute in ("code", "status_code", "status"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    return None


def is_daily_quota_message(message: str) -> bool:
    """Return True when a 429 message points at a per-day limit."""
    lowered = message.lower()
    return any(marker in lowered for marker in ("perday", "per day", "requests per day"))


def retry_delay_from_message(message: str) -> float | None:
    """Pull a suggested retry delay such as 'retryDelay': '23s' out of an error message."""
    import re

    match = re.search(r"(?:retryDelay|retry_delay|retry in|try again in)['\"]?:?\s*['\"]?(\d+(?:\.\d+)?)s", message)
    return float(match.group(1)) + 1.0 if match else None
