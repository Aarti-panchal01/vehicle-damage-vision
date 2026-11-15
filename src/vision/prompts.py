"""Loading versioned prompt files from prompts/vision and turning them into request parts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.vision.providers.base import ContentPart, ImageInput
from src.vision.vocab import DAMAGE_TYPES, PARTS, QUALITY_ISSUES, SEVERITIES

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = REPO_ROOT / "prompts" / "vision"
EXAMPLE_IMAGE_DIR = REPO_ROOT / "data" / "cardd_eval" / "images"
FEW_SHOT_PLACEHOLDER = "{{FEW_SHOT_EXAMPLES}}"
REPAIR_PROMPT_ID = "repair_v1"


@dataclass
class PromptTemplate:
    """One prompt version: its metadata from the front matter and its body text."""

    id: str
    strategy: str
    body: str
    include_analysis: bool = False
    few_shot_examples: list[str] = field(default_factory=list)
    examples_dir: str = "examples"


def list_prompt_versions(prompt_dir: Path = PROMPT_DIR) -> list[str]:
    """Return every assessment prompt id (v0_..., v1_...) found on disk, sorted."""
    return sorted(path.stem for path in prompt_dir.glob("v*.md"))


def load_prompt(prompt_id: str, prompt_dir: Path = PROMPT_DIR) -> PromptTemplate:
    """Read prompts/vision/<prompt_id>.md and parse its front matter."""
    text = (prompt_dir / f"{prompt_id}.md").read_text(encoding="utf-8")
    meta, body = split_front_matter(text)
    return PromptTemplate(
        id=meta.get("id", prompt_id),
        strategy=meta.get("strategy", "unknown"),
        body=body.strip(),
        include_analysis=meta.get("include_analysis", False),
        few_shot_examples=meta.get("few_shot_examples", []),
        examples_dir=meta.get("examples_dir", "examples"),
    )


def split_front_matter(text: str) -> tuple[dict, str]:
    """Split a '---' delimited header of key: value lines (values parsed as JSON when possible)."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = lines.index("---", 1)
    meta: dict = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        raw_value = raw_value.strip()
        try:
            meta[key.strip()] = json.loads(raw_value)
        except json.JSONDecodeError:
            meta[key.strip()] = raw_value
    return meta, "\n".join(lines[end + 1 :])


def fill_vocabulary(text: str, extra: dict[str, str] | None = None) -> str:
    """Replace {{PARTS}}-style placeholders with the fixed vocabularies and any extra values."""
    values = {
        "PARTS": ", ".join(PARTS),
        "DAMAGE_TYPES": ", ".join(DAMAGE_TYPES),
        "SEVERITIES": ", ".join(SEVERITIES),
        "QUALITY_ISSUES": ", ".join(QUALITY_ISSUES),
    }
    values.update(extra or {})
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def build_request_parts(
    template: PromptTemplate,
    images: list[ImageInput],
    user_description: str,
    prompt_dir: Path = PROMPT_DIR,
    example_image_dir: Path = EXAMPLE_IMAGE_DIR,
) -> list[ContentPart]:
    """Build the ordered text/image parts for one assessment request."""
    description = user_description.strip() or "No description provided"
    body = fill_vocabulary(
        template.body,
        {"NUM_IMAGES": str(len(images)), "USER_DESCRIPTION": description.replace('"', "'")},
    )
    parts: list[ContentPart] = []
    if FEW_SHOT_PLACEHOLDER in body:
        before, after = body.split(FEW_SHOT_PLACEHOLDER, 1)
        parts.append(before.rstrip())
        parts.extend(
            few_shot_parts(template.few_shot_examples, prompt_dir / template.examples_dir, example_image_dir)
        )
        if after.strip():
            parts.append(after.strip())
        parts.append("Now assess the photos for this claim.")
    else:
        parts.append(body)
    if len(images) == 1 and template.strategy == "baseline":
        parts.append(images[0])
        return parts
    for index, image in enumerate(images):
        parts.append(f"Photo {index}:")
        parts.append(image)
    return parts


def few_shot_parts(example_ids: list[str], answers_dir: Path, example_image_dir: Path) -> list[ContentPart]:
    """Return image + answer pairs for each worked example."""
    parts: list[ContentPart] = []
    for number, example_id in enumerate(example_ids, start=1):
        image_bytes = (example_image_dir / f"{example_id}.jpg").read_bytes()
        answer = json.loads((answers_dir / f"{example_id}.json").read_text(encoding="utf-8"))
        parts.append(f"Worked example {number}. This example has 1 photo, numbered 0.")
        parts.append(ImageInput(image_bytes))
        parts.append(f"Correct answer for worked example {number}:\n{json.dumps(answer, indent=1)}")
    return parts


def build_repair_prompt(previous_reply: str, error: str, num_images: int, prompt_dir: Path = PROMPT_DIR) -> str:
    """Build the text-only follow-up that asks the model to fix an invalid reply."""
    template = load_prompt(REPAIR_PROMPT_ID, prompt_dir)
    return fill_vocabulary(
        template.body,
        {
            "ERROR": error,
            "PREVIOUS_REPLY": previous_reply.strip()[:6000] or "(empty reply)",
            "MAX_IMAGE_INDEX": str(max(num_images - 1, 0)),
        },
    )
