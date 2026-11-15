import json

import pytest
from pydantic import ValidationError

from src.vision.schema import (
    DamageReport,
    VisionOutput,
    contract_a_json_schema,
    vision_output_json_schema,
)
from src.vision.vocab import PARTS, part_family

VALID_DAMAGE = {
    "part": "rear_bumper",
    "damage_type": "dent",
    "severity": "moderate",
    "confidence": 0.82,
    "image_index": 0,
    "notes": "Dent around 15 cm wide near the left corner",
}


def test_valid_output_is_accepted():
    output = VisionOutput.model_validate({"damages": [VALID_DAMAGE], "image_quality_flags": ["image_0_blurry"]})
    assert output.damages[0].part == "rear_bumper"


def test_empty_damages_is_valid():
    assert VisionOutput.model_validate({"damages": [], "image_quality_flags": []}).damages == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("part", "headlight"),
        ("damage_type", "smashed"),
        ("severity", "critical"),
        ("confidence", 1.4),
        ("image_index", -1),
    ],
)
def test_out_of_vocabulary_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        VisionOutput.model_validate({"damages": [{**VALID_DAMAGE, field: value}]})


@pytest.mark.parametrize("flag", ["blurry", "image_one_blurry", "image_0_foggy"])
def test_bad_quality_flags_are_rejected(flag):
    with pytest.raises(ValidationError):
        VisionOutput.model_validate({"damages": [], "image_quality_flags": [flag]})


def test_extra_keys_like_analysis_are_ignored():
    output = VisionOutput.model_validate({"analysis": "front view", "damages": [], "image_quality_flags": []})
    assert "analysis" not in output.model_dump()


def test_contract_a_matches_team_plan_example():
    example = {
        "claim_id": "CLM-20261020-001",
        "vehicle": {"make": "Maruti Suzuki", "model": "Swift", "year": 2021, "fuel": "petrol"},
        "user_description": "Hit a pole while reversing",
        "damages": [VALID_DAMAGE],
        "image_quality_flags": ["image_1_blurry"],
        "model_used": "gemini-flash",
        "prompt_strategy": "few_shot",
    }
    assert DamageReport.model_validate(example).model_dump() == example


def test_claim_id_format_is_enforced():
    with pytest.raises(ValidationError):
        DamageReport.model_validate(
            {
                "claim_id": "claim-1",
                "vehicle": {"make": "Tata", "model": "Nexon", "year": 2022, "fuel": "diesel"},
                "user_description": "",
                "damages": [],
                "image_quality_flags": [],
                "model_used": "m",
                "prompt_strategy": "p",
            }
        )


def test_strict_json_schema_lists_every_property_as_required():
    schema = vision_output_json_schema(include_analysis=True)
    assert schema["required"] == ["analysis", "damages", "image_quality_flags"]
    item = schema["properties"]["damages"]["items"]
    assert set(item["required"]) == set(item["properties"])
    assert item["additionalProperties"] is False
    assert item["properties"]["part"]["enum"] == list(PARTS)
    json.dumps(schema)


def test_contract_a_json_schema_is_serialisable():
    schema = contract_a_json_schema()
    assert schema["title"].startswith("Contract A")
    assert "damages" in schema["properties"]


@pytest.mark.parametrize(
    "part,family",
    [
        ("rear_left_tyre", "tyre"),
        ("front_right_door", "door"),
        ("left_headlamp", "headlamp"),
        ("right_quarter_panel", "quarter_panel"),
        ("front_bumper", "front_bumper"),
        ("windshield", "windshield"),
    ],
)
def test_part_family_drops_corner(part, family):
    assert part_family(part) == family
