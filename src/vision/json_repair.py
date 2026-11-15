"""Turning raw model text into a validated VisionOutput, and describing what went wrong when it fails."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from src.vision.schema import VisionOutput

CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


@dataclass
class ParseResult:
    """Outcome of parsing one model reply."""

    output: VisionOutput | None
    error: str | None
    parsed_json: dict | None = None

    @property
    def ok(self) -> bool:
        return self.output is not None


def find_json_object(text: str) -> str | None:
    """Return the last complete top-level {...} block in text, or None.

    Prefers the content of a ```json fence when present. The last block is
    used because chain-of-thought replies may mention braces before the answer.
    """
    cleaned = THINK_BLOCK_PATTERN.sub("", text)
    fenced = CODE_FENCE_PATTERN.findall(cleaned)
    candidates = [block for block in fenced if "{" in block] or [cleaned]
    for candidate in reversed(candidates):
        block = last_balanced_object(candidate)
        if block is not None:
            return block
    return None


def last_balanced_object(text: str) -> str | None:
    """Scan text and return the last balanced top-level JSON object, respecting strings."""
    depth = 0
    start = None
    in_string = False
    escaped = False
    last_block = None
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                last_block = text[start : index + 1]
    return last_block


def remove_trailing_commas(json_text: str) -> str:
    """Drop commas placed right before a closing bracket, a common small-model mistake."""
    return re.sub(r",(\s*[}\]])", r"\1", json_text)


def parse_vision_output(text: str, num_images: int) -> ParseResult:
    """Parse and validate model text against VisionOutput.

    Also checks that every image_index and quality-flag index points at a real
    photo. Returns a ParseResult whose error text is written to be sent back to
    the model in a repair request.
    """
    block = find_json_object(text or "")
    if block is None:
        return ParseResult(None, "The reply contained no JSON object. Return exactly one JSON object.")
    try:
        data = json.loads(block)
    except json.JSONDecodeError:
        try:
            data = json.loads(remove_trailing_commas(block))
        except json.JSONDecodeError as error:
            return ParseResult(None, f"The JSON could not be parsed: {error.msg} at position {error.pos}.")
    if not isinstance(data, dict):
        return ParseResult(None, "The top-level JSON value must be an object.")
    try:
        output = VisionOutput.model_validate(data)
    except ValidationError as error:
        return ParseResult(None, format_validation_error(error), parsed_json=data)
    index_error = check_image_indexes(output, num_images)
    if index_error:
        return ParseResult(None, index_error, parsed_json=data)
    return ParseResult(output, None, parsed_json=data)


def format_validation_error(error: ValidationError) -> str:
    """Summarise a Pydantic error as short lines the model can act on."""
    lines = []
    for issue in error.errors()[:10]:
        location = ".".join(str(part) for part in issue["loc"])
        lines.append(f"- {location}: {issue['msg']}")
    return "The JSON did not match the required schema:\n" + "\n".join(lines)


def check_image_indexes(output: VisionOutput, num_images: int) -> str | None:
    """Return an error message if any index refers to a photo that was not sent."""
    bad_damage_indexes = sorted({d.image_index for d in output.damages if d.image_index >= num_images})
    bad_flags = [
        flag for flag in output.image_quality_flags if int(flag.split("_")[1]) >= num_images
    ]
    if bad_damage_indexes or bad_flags:
        return (
            f"Only {num_images} photo(s) were sent, numbered 0 to {num_images - 1}. "
            f"Invalid image_index values: {bad_damage_indexes}; invalid flags: {bad_flags}."
        )
    return None
