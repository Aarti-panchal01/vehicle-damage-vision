"""Role 1 vision module: car photos to a validated Contract A damage report.

Typical use:

    from src.vision import assess_damage, load_image, make_provider

    result = assess_damage(
        images=[load_image("photo.jpg")],
        vehicle={"make": "Maruti Suzuki", "model": "Swift", "year": 2021, "fuel": "petrol"},
        provider=make_provider("gemini"),
        user_description="Hit a pole while reversing",
    )
    contract_a = result.report.model_dump() if result.ok else result.error.model_dump()
"""

from __future__ import annotations

from pathlib import Path

from src.vision.assess import AssessmentResult, assess_damage, merge_damages
from src.vision.providers import ImageInput, make_provider
from src.vision.schema import Damage, DamageReport, Vehicle, VisionError, VisionOutput

MIME_BY_SUFFIX = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def load_image(path: str | Path) -> ImageInput:
    """Read an image file from disk into an ImageInput."""
    path = Path(path)
    return ImageInput(data=path.read_bytes(), mime_type=MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg"))


__all__ = [
    "AssessmentResult",
    "Damage",
    "DamageReport",
    "ImageInput",
    "Vehicle",
    "VisionError",
    "VisionOutput",
    "assess_damage",
    "load_image",
    "make_provider",
    "merge_damages",
]
