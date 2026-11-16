
import csv
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COST_FOLDER = PROJECT_ROOT / "src" / "cost"
sys.path.insert(0, str(COST_FOLDER))

import cost_engine  # noqa: E402


@pytest.fixture
def demo_contract():
    """Load the project's actual Contract A demo input."""
    input_file = PROJECT_ROOT / "mocks" / "contract_a_demo.json"

    with open(input_file, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_csv(path, headers, rows):
    """Write temporary CSV data for isolated tests."""
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def prepared_cost_data(tmp_path, monkeypatch):
    """Provide sample prices and labour rates only for testing."""
    parts_file = tmp_path / "parts_prices.csv"
    labour_file = tmp_path / "labour_rates.csv"

    write_csv(
        parts_file,
        [
            "make", "model", "year_range", "part", "material",
            "part_price_inr", "paint_cost_inr",
            "source_url", "date_accessed",
        ],
        [
            {
                "make": "Maruti Suzuki",
                "model": "Swift",
                "year_range": "2021-2022",
                "part": "front_bumper",
                "material": "plastic",
                "part_price_inr": "2250",
                "paint_cost_inr": "100",
                "source_url": "TEST DATA - NOT A REAL QUOTATION",
                "date_accessed": "2026-10-09",
            }
        ],
    )

    write_csv(
        labour_file,
        [
            "garage_name", "city", "service", "vehicle_model",
            "rate_inr", "rate_unit", "includes_paint_material",
            "source", "date_accessed",
        ],
        [
            {
                "garage_name": "Test Garage",
                "city": "Bengaluru",
                "service": "front_bumper_repair_labour",
                "vehicle_model": "Swift",
                "rate_inr": "500",
                "rate_unit": "per_job",
                "includes_paint_material": "no",
                "source": "TEST DATA - NOT A REAL QUOTATION",
                "date_accessed": "2026-10-09",
            }
        ],
    )

    monkeypatch.setattr(cost_engine, "PARTS_FILE", parts_file)
    monkeypatch.setattr(cost_engine, "LABOUR_FILE", labour_file)


def test_contract_b_has_required_top_level_keys(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)

    assert set(result.keys()) == {
        "claim_id",
        "currency",
        "vehicle_age_years",
        "line_items",
        "totals",
        "unpriced_parts",
    }


def test_demo_claim_id_and_currency_are_preserved(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)

    assert result["claim_id"] == "CLM-DEMO-001"
    assert result["currency"] == "INR"


def test_moderate_bumper_dent_creates_a_repair_line_item(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)

    assert len(result["line_items"]) == 1

    item = result["line_items"][0]

    assert item["part"] == "front_bumper"
    assert item["action"] == "repair"
    assert item["material"] == "plastic"


def test_line_item_contains_required_fields(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)
    item = result["line_items"][0]

    required_fields = {
        "part",
        "action",
        "material",
        "part_cost",
        "labour_cost",
        "paint_cost",
        "depreciation_pct",
        "depreciation_amount",
        "claimable_amount",
        "price_source",
    }

    assert set(item.keys()) == required_fields


def test_costs_and_totals_are_calculated_consistently(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)
    item = result["line_items"][0]

    # Repairing a part must not charge the full replacement part price.
    assert item["part_cost"] == 0
    assert item["labour_cost"] == 500
    assert item["paint_cost"] == 100

    assert item["depreciation_pct"] == 50
    assert item["depreciation_amount"] == 12.5
    assert item["claimable_amount"] == 587.5

    assert result["totals"]["gross"] == 600
    assert result["totals"]["depreciation"] == 12.5
    assert result["totals"]["claimable"] == 587.5


def test_claimable_equals_gross_minus_depreciation(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)
    totals = result["totals"]

    assert totals["claimable"] == round(
        totals["gross"] - totals["depreciation"], 2
    )


def test_complete_demo_has_no_unpriced_parts(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)

    assert result["unpriced_parts"] == []


def test_missing_labour_rate_is_reported(
    demo_contract, prepared_cost_data, tmp_path, monkeypatch
):
    empty_labour_file = tmp_path / "empty_labour_rates.csv"

    write_csv(
        empty_labour_file,
        [
            "garage_name", "city", "service", "vehicle_model",
            "rate_inr", "rate_unit", "includes_paint_material",
            "source", "date_accessed",
        ],
        [],
    )

    monkeypatch.setattr(
        cost_engine, "LABOUR_FILE", empty_labour_file
    )

    result = cost_engine.calculate_estimate(demo_contract)

    assert result["line_items"] == []
    assert result["unpriced_parts"] == ["front_bumper"]
    assert result["totals"] == {
        "gross": 0,
        "depreciation": 0,
        "claimable": 0,
    }


def test_duplicate_damage_observations_create_one_physical_cost_line(
    demo_contract, prepared_cost_data
):
    demo_contract["damages"] = [
        {"part": "front_bumper", "damage_type": "dent", "severity": "moderate", "confidence": 0.9, "image_index": 0},
        {"part": "front_bumper", "damage_type": "scratch", "severity": "moderate", "confidence": 0.9, "image_index": 0},
    ]
    result = cost_engine.calculate_estimate(demo_contract)
    assert len(result["line_items"]) == 1
    assert result["line_items"][0]["part"] == "front_bumper"
    assert result["line_items"][0]["action"] == "repair"


def test_replacement_dominates_repair_for_same_part(
    demo_contract, prepared_cost_data, tmp_path, monkeypatch
):
    demo_contract["damages"] = [
        {"part": "front_bumper", "damage_type": "dent", "severity": "severe", "confidence": 0.9, "image_index": 0},
        {"part": "front_bumper", "damage_type": "scratch", "severity": "moderate", "confidence": 0.9, "image_index": 0},
    ]
    labour_file = tmp_path / "replacement_labour.csv"
    write_csv(
        labour_file,
        [
            "garage_name", "city", "service", "vehicle_model",
            "rate_inr", "rate_unit", "includes_paint_material",
            "source", "date_accessed",
        ],
        [{
            "garage_name": "Test Garage", "city": "Bengaluru",
            "service": "front_bumper_replace_labour", "vehicle_model": "Swift",
            "rate_inr": "900", "rate_unit": "per_job",
            "includes_paint_material": "no", "source": "test fixture",
            "date_accessed": "2026-11-09",
        }],
    )
    monkeypatch.setattr(cost_engine, "LABOUR_FILE", labour_file)
    result = cost_engine.calculate_estimate(demo_contract)
    assert len(result["line_items"]) == 1
    assert result["line_items"][0]["action"] == "replace"
    assert result["line_items"][0]["part_cost"] == 2250


def test_two_garage_rates_use_median_not_ambiguous_duplicate_error():
    rates = [
        {"garage_name": "Garage A", "service": "front_bumper_repair_labour",
         "vehicle_model": "Swift", "rate_inr": "500", "rate_unit": "per_job"},
        {"garage_name": "Garage B", "service": "front_bumper_repair_labour",
         "vehicle_model": "Swift", "rate_inr": "700", "rate_unit": "per_job"},
    ]
    assert cost_engine.get_labour_cost("Swift", "front_bumper", "repair", rates) == 600


def test_hourly_labour_rate_is_not_used_without_duration():
    rates = [
        {"garage_name": "Garage A", "service": "front_bumper_repair_labour",
         "vehicle_model": "Swift", "rate_inr": "500", "rate_unit": "per_hour"},
    ]
    assert cost_engine.get_labour_cost("Swift", "front_bumper", "repair", rates) is None


def test_labour_source_is_included_in_price_source(
    demo_contract, prepared_cost_data
):
    result = cost_engine.calculate_estimate(demo_contract)
    assert "TEST DATA - NOT A REAL QUOTATION" in result["line_items"][0]["price_source"]


def test_left_fender_does_not_reuse_right_only_part_price():
    vehicle = {"make": "Maruti Suzuki", "model": "Swift", "year": 2021}
    prices = [{
        "make": "Maruti Suzuki", "model": "Swift",
        "year_range": "2021-2022", "part": "front_fender_right",
        "material": "metal", "part_price_inr": "1565",
    }]
    assert cost_engine.find_part_price(vehicle, "front_left_fender", prices) is None
    assert cost_engine.find_part_price(vehicle, "front_right_fender", prices) is not None


def test_two_garage_paint_quotes_use_median_only_when_material_is_included():
    rates = [
        {"garage_name": "Paint A", "service": "full_panel_painting",
         "vehicle_model": "Swift", "rate_inr": "1800", "rate_unit": "per_panel",
         "includes_paint_material": "yes"},
        {"garage_name": "Paint B", "service": "full_panel_painting",
         "vehicle_model": "Swift", "rate_inr": "2200", "rate_unit": "per_panel",
         "includes_paint_material": "yes"},
    ]
    assert cost_engine.get_paint_cost("Swift", "front_bumper", rates) == 2000


def test_paint_quote_without_material_is_not_used_as_complete_paint_cost():
    rates = [
        {"garage_name": "Paint A", "service": "full_panel_painting",
         "vehicle_model": "Swift", "rate_inr": "1800", "rate_unit": "per_panel",
         "includes_paint_material": "no"},
    ]
    assert cost_engine.get_paint_cost("Swift", "front_bumper", rates) is None


def test_all_in_paint_quote_is_not_double_counted_as_repair_labour():
    rates = [
        {"garage_name": "Garage A", "service": "front_bumper_repair_labour",
         "vehicle_model": "Swift", "rate_inr": "2000", "rate_unit": "per_job",
         "includes_paint_material": "yes"},
    ]
    assert cost_engine.get_labour_cost("Swift", "front_bumper", "repair", rates) is None


def test_engine_uses_all_in_paint_rate_when_part_table_has_no_paint_price(
    demo_contract, prepared_cost_data, tmp_path, monkeypatch
):
    parts_file = tmp_path / "parts_without_paint.csv"
    write_csv(
        parts_file,
        ["make", "model", "year_range", "part", "material",
         "part_price_inr", "paint_cost_inr", "source_url", "date_accessed"],
        [{
            "make": "Maruti Suzuki", "model": "Swift", "year_range": "2021-2022",
            "part": "front_bumper", "material": "plastic", "part_price_inr": "2250",
            "paint_cost_inr": "", "source_url": "PART SOURCE",
            "date_accessed": "2026-11-09",
        }],
    )
    paint_file = tmp_path / "paint_rates.csv"
    write_csv(
        paint_file,
        ["garage_name", "city", "service", "vehicle_model", "rate_inr",
         "rate_unit", "includes_paint_material", "source", "date_accessed"],
        [{
            "garage_name": "Paint Garage", "city": "Bengaluru",
            "service": "full_panel_painting", "vehicle_model": "Swift",
            "rate_inr": "1500", "rate_unit": "per_panel",
            "includes_paint_material": "yes", "source": "PAINT QUOTE",
            "date_accessed": "2026-11-09",
        }],
    )
    monkeypatch.setattr(cost_engine, "PARTS_FILE", parts_file)
    monkeypatch.setattr(cost_engine, "PAINT_FILE", paint_file)
    result = cost_engine.calculate_estimate(demo_contract)
    item = result["line_items"][0]
    assert item["paint_cost"] == 1500
    assert "PAINT QUOTE" in item["price_source"]


def test_existing_role1_sample_outputs_validate_contract_b_schema():
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator

    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas" / "contract_b.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    outputs = sorted((root / "outputs" / "role2_contract_b_samples").glob("*_contract_b.json"))
    assert len(outputs) == 5
    for output in outputs:
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert list(validator.iter_errors(payload)) == []
