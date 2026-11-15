"""The Role 1 pipeline: photos in, Contract A damage report (or a structured error) out."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from src.vision.json_repair import parse_vision_output
from src.vision.prompts import PROMPT_DIR, build_repair_prompt, build_request_parts, load_prompt
from src.vision.providers.base import (
    ImageInput,
    ProviderError,
    ProviderReply,
    QuotaExhaustedError,
    VisionProvider,
)
from src.vision.schema import Damage, DamageReport, Vehicle, VisionError, VisionOutput, vision_output_json_schema
from src.vision.vocab import SEVERITY_RANK

MAX_IMAGES = 5
DEFAULT_MAX_RETRIES = 2
DEFAULT_PROMPT_ID = "v4_best"


@dataclass
class Attempt:
    """One call to the model: the first request or a repair request."""

    kind: str
    reply: ProviderReply
    valid: bool
    error: str | None


@dataclass
class AssessmentResult:
    """Everything one assessment produced, including the per-attempt record used by the evaluation."""

    report: DamageReport | None
    error: VisionError | None
    attempts: list[Attempt] = field(default_factory=list)
    vision_output: VisionOutput | None = None

    @property
    def ok(self) -> bool:
        return self.report is not None

    @property
    def first_try_valid(self) -> bool:
        return bool(self.attempts) and self.attempts[0].valid

    @property
    def retries_used(self) -> int:
        return max(len(self.attempts) - 1, 0)

    @property
    def input_tokens(self) -> int:
        return sum(attempt.reply.input_tokens for attempt in self.attempts)

    @property
    def output_tokens(self) -> int:
        return sum(attempt.reply.output_tokens + attempt.reply.thinking_tokens for attempt in self.attempts)

    @property
    def latency_s(self) -> float:
        return round(sum(attempt.reply.latency_s for attempt in self.attempts), 3)


def new_claim_id(today: date | None = None) -> str:
    """Make a claim id in the CLM-YYYYMMDD-NNN format used by all contracts."""
    day = (today or date.today()).strftime("%Y%m%d")
    return f"CLM-{day}-{random.randint(1, 999):03d}"


def prompt_strategy_label(prompt_id: str, enforce_schema: bool) -> str:
    """Name written into Contract A's prompt_strategy field, e.g. 'v1_structured+schema'."""
    return f"{prompt_id}+schema" if enforce_schema else prompt_id


def assess_damage(
    images: list[ImageInput],
    vehicle: Vehicle | dict,
    provider: VisionProvider,
    user_description: str = "",
    prompt_id: str = DEFAULT_PROMPT_ID,
    enforce_schema: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
    claim_id: str | None = None,
    merge: bool = True,
    prompt_dir=PROMPT_DIR,
) -> AssessmentResult:
    """Assess 1 to 5 photos and return a Contract A report or a VisionError.

    The model reply is validated with Pydantic. If it is invalid, the error is
    sent back to the model in a text-only repair request, at most max_retries
    times. Damages of the same part and type seen in several photos are merged.
    """
    claim_id = claim_id or new_claim_id()
    strategy = prompt_strategy_label(prompt_id, enforce_schema)
    vehicle_model = vehicle if isinstance(vehicle, Vehicle) else Vehicle.model_validate(vehicle)

    def failure(code: str, message: str, attempts: list[Attempt], last_raw: str | None) -> AssessmentResult:
        error = VisionError(
            claim_id=claim_id,
            error_code=code,
            message=message,
            attempts=len(attempts),
            last_raw_output=last_raw,
            model_used=provider.model,
            prompt_strategy=strategy,
        )
        return AssessmentResult(report=None, error=error, attempts=attempts)

    if not 1 <= len(images) <= MAX_IMAGES:
        return failure("bad_input", f"Send between 1 and {MAX_IMAGES} photos, got {len(images)}.", [], None)

    template = load_prompt(prompt_id, prompt_dir)
    schema = vision_output_json_schema(template.include_analysis) if enforce_schema else None
    parts = build_request_parts(template, images, user_description, prompt_dir=prompt_dir)
    attempts: list[Attempt] = []

    try:
        reply = provider.generate(parts, schema)
    except ProviderError as error:
        return failure(error_code_for(error), str(error), attempts, None)
    parsed = parse_vision_output(reply.text, len(images))
    attempts.append(Attempt("initial", reply, parsed.ok, parsed.error))

    while not parsed.ok and len(attempts) <= max_retries:
        repair_text = build_repair_prompt(reply.text, parsed.error or "", len(images), prompt_dir)
        try:
            reply = provider.generate([repair_text], None)
        except ProviderError as error:
            return failure(error_code_for(error), str(error), attempts, attempts[-1].reply.text)
        parsed = parse_vision_output(reply.text, len(images))
        attempts.append(Attempt("repair", reply, parsed.ok, parsed.error))

    if not parsed.ok or parsed.output is None:
        return failure("invalid_model_output", parsed.error or "invalid output", attempts, reply.text)

    damages = merge_damages(parsed.output.damages) if merge else list(parsed.output.damages)
    report = DamageReport(
        claim_id=claim_id,
        vehicle=vehicle_model,
        user_description=user_description,
        damages=damages,
        image_quality_flags=sorted(set(parsed.output.image_quality_flags)),
        model_used=provider.model,
        prompt_strategy=strategy,
    )
    return AssessmentResult(report=report, error=None, attempts=attempts, vision_output=parsed.output)


def error_code_for(error: ProviderError) -> str:
    """Map a provider exception to the VisionError code shown to callers."""
    return "quota_exhausted" if isinstance(error, QuotaExhaustedError) else "provider_error"


def merge_damages(damages: list[Damage]) -> list[Damage]:
    """Keep one entry per (part, damage_type) across photos.

    The kept entry is the most severe one (ties broken by confidence); its
    confidence becomes the highest seen for that part and type.
    """
    best: dict[tuple[str, str], Damage] = {}
    for damage in damages:
        key = (damage.part, damage.damage_type)
        current = best.get(key)
        if current is None:
            best[key] = damage
            continue
        rank_new = (SEVERITY_RANK[damage.severity], damage.confidence)
        rank_old = (SEVERITY_RANK[current.severity], current.confidence)
        winner = damage if rank_new > rank_old else current
        best[key] = winner.model_copy(update={"confidence": max(damage.confidence, current.confidence)})
    return list(best.values())
