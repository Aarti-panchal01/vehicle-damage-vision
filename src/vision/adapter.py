"""Byte-oriented adapter for callers that need a plain Contract A or error dict."""

from __future__ import annotations

from src.vision import assess_damage, make_provider
from src.vision.assess import DEFAULT_PROMPT_ID, MAX_IMAGES, new_claim_id
from src.vision.providers import ImageInput
from src.vision.schema import Vehicle, VisionError


def run_vision(
    photo_bytes_list: list[bytes],
    vehicle: Vehicle | dict,
    description: str,
    claim_id: str | None,
) -> dict:
    """Assess uploaded photo bytes and return a Contract A or VisionError dictionary."""
    resolved_claim_id = claim_id if isinstance(claim_id, str) and claim_id else new_claim_id()
    try:
        if (
            not isinstance(photo_bytes_list, list)
            or not 1 <= len(photo_bytes_list) <= MAX_IMAGES
            or any(not isinstance(photo, bytes) for photo in photo_bytes_list)
        ):
            return _error(resolved_claim_id, "bad_input", f"Send 1 to {MAX_IMAGES} photos as bytes.")
        if not isinstance(description, str):
            return _error(resolved_claim_id, "bad_input", "Description must be text.")

        try:
            vehicle_model = Vehicle.model_validate(vehicle)
        except (TypeError, ValueError):
            return _error(resolved_claim_id, "bad_input", "Vehicle details are invalid.")
        result = assess_damage(
            [ImageInput(photo) for photo in photo_bytes_list],
            vehicle_model,
            make_provider("gemini"),
            user_description=description,
            prompt_id=DEFAULT_PROMPT_ID,
            claim_id=resolved_claim_id,
        )
        if result.report is not None:
            return result.report.model_dump(mode="json")
        if result.error is not None:
            return result.error.model_dump(mode="json")
        raise RuntimeError("Vision assessment returned neither a report nor an error.")
    except Exception as error:
        return _error(
            resolved_claim_id,
            "provider_error",
            f"Vision assessment failed ({type(error).__name__}).",
        )


def _error(claim_id: str, code: str, message: str) -> dict:
    return VisionError(
        claim_id=claim_id,
        error_code=code,
        message=message,
        attempts=0,
        model_used="unknown",
        prompt_strategy=DEFAULT_PROMPT_ID,
    ).model_dump(mode="json")
