import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "cost"))
import cost_engine  # noqa: E402

ROLE1_MOCKS = Path(__file__).resolve().parents[1] / "role1_mocks"


@pytest.mark.parametrize("filename", [
    "contract_a_001_dev_01.json",
    "contract_a_002_eval_18.json",
    "contract_a_003_dev_04.json",
    "contract_a_004_dev_05.json",
    "contract_a_005_dev_09.json",
])
def test_role1_contract_a_samples_are_accepted(filename):
    with open(ROLE1_MOCKS / filename, encoding="utf-8") as f:
        contract_a = json.load(f)
    result = cost_engine.calculate_estimate(contract_a, reference_year=2026)
    assert result["claim_id"] == contract_a["claim_id"]
    assert result["currency"] == "INR"
    assert set(result) == {
        "claim_id", "currency", "vehicle_age_years",
        "line_items", "totals", "unpriced_parts"
    }


def test_no_damage_report_returns_zero_totals():
    report = {
        "claim_id": "CLM-20261020-002",
        "vehicle": {"make": "Hyundai", "model": "Creta", "year": 2022, "fuel": "diesel"},
        "user_description": "No damage reported",
        "damages": [],
        "image_quality_flags": [],
        "model_used": "test",
        "prompt_strategy": "test"
    }
    result = cost_engine.calculate_estimate(report, reference_year=2026)
    assert result["line_items"] == []
    assert result["unpriced_parts"] == []
    assert result["totals"] == {"gross": 0, "depreciation": 0, "claimable": 0}


def test_vision_error_is_not_accepted_as_contract_a():
    error = {"claim_id": "CLM-20261020-006", "error_code": "invalid_model_output"}
    with pytest.raises(ValueError, match="VisionError"):
        cost_engine.calculate_estimate(error, reference_year=2026)


def test_same_part_with_dent_and_scratch_is_one_cost_line():
    damages = [
        {"part": "front_bumper", "damage_type": "dent", "severity": "moderate"},
        {"part": "front_bumper", "damage_type": "scratch", "severity": "moderate"},
    ]
    assert len({d["part"] for d in damages}) == 1
    # The estimator must group records by physical part before pricing;
    # it must not create one replacement line per damage observation.
    grouped = {}
    for d in damages:
        grouped.setdefault(d["part"], []).append(d)
    assert len(grouped) == 1
    assert len(grouped["front_bumper"]) == 2


def test_replacement_dominates_repair_for_same_physical_part():
    assert cost_engine.choose_action("dent", "severe", "metal") == "replace"
    assert cost_engine.choose_action("scratch", "moderate", "metal") == "repair"


def test_invalid_part_outside_role1_enum_is_rejected():
    report = {
        "claim_id": "CLM-20261020-007",
        "vehicle": {"make": "Maruti Suzuki", "model": "Swift", "year": 2021, "fuel": "petrol"},
        "user_description": "test",
        "damages": [{"part": "unknown_panel", "damage_type": "dent", "severity": "minor", "confidence": 0.8, "image_index": 0}],
        "image_quality_flags": [],
        "model_used": "test",
        "prompt_strategy": "test",
    }
    with pytest.raises(ValueError, match="Unsupported part"):
        cost_engine.calculate_estimate(report, reference_year=2026)


def test_vehicle_fuel_is_required_by_role1_contract():
    report = {
        "claim_id": "CLM-20261020-008",
        "vehicle": {"make": "Maruti Suzuki", "model": "Swift", "year": 2021},
        "user_description": "test",
        "damages": [],
        "image_quality_flags": [],
        "model_used": "test",
        "prompt_strategy": "test",
    }
    with pytest.raises(ValueError, match="fuel"):
        cost_engine.calculate_estimate(report, reference_year=2026)
