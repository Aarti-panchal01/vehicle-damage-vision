import json

from src.vision.assess import assess_damage, merge_damages, new_claim_id
from src.vision.prompts import build_request_parts, list_prompt_versions, load_prompt, split_front_matter
from src.vision.providers import ImageInput, MockProvider
from src.vision.providers.cache import CachedProvider
from src.vision.schema import Damage

VEHICLE = {"make": "Hyundai", "model": "Creta", "year": 2022, "fuel": "petrol"}
IMAGE = ImageInput(b"\xff\xd8fake-jpeg")
GOOD_REPLY = json.dumps(
    {
        "damages": [{"part": "front_bumper", "damage_type": "scratch", "severity": "minor", "confidence": 0.7,
                     "image_index": 0, "notes": "Scuff on the lower lip"}],
        "image_quality_flags": [],
    }
)


def damage(part, damage_type, severity, confidence=0.5, image_index=0):
    return Damage(part=part, damage_type=damage_type, severity=severity, confidence=confidence,
                  image_index=image_index, notes="")


def test_valid_first_reply_gives_contract_a():
    provider = MockProvider([GOOD_REPLY])
    result = assess_damage([IMAGE], VEHICLE, provider, prompt_id="v1_structured", claim_id="CLM-20261008-001")
    assert result.ok and result.first_try_valid and result.retries_used == 0
    report = result.report.model_dump()
    assert report["claim_id"] == "CLM-20261008-001"
    assert report["vehicle"]["model"] == "Creta"
    assert report["prompt_strategy"] == "v1_structured"
    assert report["model_used"] == "mock-vlm"


def test_invalid_reply_is_repaired_with_a_text_only_request():
    provider = MockProvider(["The bumper is scratched.", GOOD_REPLY])
    result = assess_damage([IMAGE], VEHICLE, provider, prompt_id="v0_baseline")
    assert result.ok and not result.first_try_valid and result.retries_used == 1
    repair_parts, repair_schema = provider.requests[1]
    assert len(repair_parts) == 1 and isinstance(repair_parts[0], str)
    assert "The bumper is scratched." in repair_parts[0]
    assert repair_schema is None


def test_gives_structured_error_after_max_retries():
    provider = MockProvider(["nope", "still nope", "never"])
    result = assess_damage([IMAGE], VEHICLE, provider, prompt_id="v1_structured", max_retries=2)
    assert not result.ok
    assert result.error.error_code == "invalid_model_output"
    assert result.error.attempts == 3
    assert result.error.last_raw_output == "never"


def test_one_retry_setting_stops_after_two_attempts():
    provider = MockProvider(["nope", "still nope"])
    result = assess_damage([IMAGE], VEHICLE, provider, prompt_id="v1_structured", max_retries=1)
    assert not result.ok and result.error.attempts == 2


def test_too_many_photos_is_a_bad_input_error():
    result = assess_damage([IMAGE] * 6, VEHICLE, MockProvider([]), prompt_id="v1_structured")
    assert result.error.error_code == "bad_input"


def test_schema_enforcement_passes_schema_and_labels_strategy():
    provider = MockProvider([GOOD_REPLY])
    result = assess_damage([IMAGE], VEHICLE, provider, prompt_id="v1_structured", enforce_schema=True)
    assert provider.requests[0][1]["required"] == ["damages", "image_quality_flags"]
    assert result.report.prompt_strategy == "v1_structured+schema"


def test_merge_keeps_highest_severity_per_part_and_type():
    merged = merge_damages(
        [
            damage("front_bumper", "dent", "minor", 0.9, image_index=0),
            damage("front_bumper", "dent", "severe", 0.4, image_index=1),
            damage("front_bumper", "scratch", "minor", 0.6),
        ]
    )
    by_key = {(d.part, d.damage_type): d for d in merged}
    assert len(merged) == 2
    assert by_key[("front_bumper", "dent")].severity == "severe"
    assert by_key[("front_bumper", "dent")].image_index == 1
    assert by_key[("front_bumper", "dent")].confidence == 0.9


def test_claim_id_format():
    assert new_claim_id().startswith("CLM-") and len(new_claim_id()) == 16


def test_all_prompt_versions_load_and_fill_placeholders(tmp_path):
    versions = list_prompt_versions()
    assert versions[:4] == ["v0_baseline", "v1_structured", "v2_fewshot", "v3_cot"]
    for example_id in ("dev_03", "dev_10"):
        (tmp_path / f"{example_id}.jpg").write_bytes(b"test-image")
    for version in versions:
        parts = build_request_parts(
            load_prompt(version),
            [IMAGE],
            "hit a pole",
            example_image_dir=tmp_path,
        )
        text = "\n".join(part for part in parts if isinstance(part, str))
        assert "{{" not in text, version


def test_few_shot_prompt_fits_groq_three_image_limit(tmp_path):
    for example_id in ("dev_03", "dev_10"):
        (tmp_path / f"{example_id}.jpg").write_bytes(b"test-image")
    parts = build_request_parts(
        load_prompt("v2_fewshot"),
        [IMAGE],
        "",
        example_image_dir=tmp_path,
    )
    assert sum(isinstance(part, ImageInput) for part in parts) <= 3


def test_front_matter_parsing():
    meta, body = split_front_matter("---\nid: v9\nfew_shot_examples: [\"a\"]\ninclude_analysis: true\n---\nHello")
    assert meta == {"id": "v9", "few_shot_examples": ["a"], "include_analysis": True}
    assert body.strip() == "Hello"


def test_cache_returns_stored_reply_without_calling_provider(tmp_path):
    inner = MockProvider([GOOD_REPLY])
    cached = CachedProvider(inner, tmp_path)
    first = cached.generate(["prompt", IMAGE])
    second = cached.generate(["prompt", IMAGE])
    assert first.text == second.text and second.from_cache and len(inner.requests) == 1


def test_retry_delay_is_read_from_gemini_and_groq_messages():
    from src.vision.providers.base import retry_delay_from_message

    assert retry_delay_from_message("Please retry in 3.79s.") == 3.79 + 1.0
    assert retry_delay_from_message("Rate limit reached. Please try again in 7.66s. Need more tokens?") == 7.66 + 1.0
    assert retry_delay_from_message("'retryDelay': '23s'") == 24.0
    assert retry_delay_from_message("no hint here") is None
