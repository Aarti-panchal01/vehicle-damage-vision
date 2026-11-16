
import sys
from pathlib import Path

import pytest

# Make the project's cost-engine module importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
COST_FOLDER = PROJECT_ROOT / "src" / "cost"
sys.path.insert(0, str(COST_FOLDER))

from cost_engine import (
    choose_action,
    get_depreciation_pct,
    get_metal_depreciation,
    load_depreciation_rules,
)


@pytest.fixture
def rules():
    """Load the project's depreciation configuration."""
    return load_depreciation_rules()


# --------------------------------------------------
# 1. REPAIR AND REPLACEMENT RULES
# --------------------------------------------------

@pytest.mark.parametrize(
    "damage_type, severity, material, expected",
    [
        ("lamp_broken", "minor", "plastic", "replace"),
        ("lamp_broken", "severe", "plastic", "replace"),
        ("glass_shatter", "severe", "glass", "replace"),
        ("scratch", "minor", "paint", "repair"),
        ("dent", "minor", "metal", "repair"),
        ("dent", "moderate", "metal", "repair"),
        ("dent", "severe", "metal", "replace"),
        ("crack", "minor", "plastic", "repair"),
        ("crack", "moderate", "plastic", "repair"),
        ("crack", "severe", "plastic", "replace"),
        ("crack", "severe", "metal", "repair"),
        ("tire_flat", "minor", "rubber", "repair"),
        ("tire_flat", "moderate", "rubber", "repair"),
        ("tire_flat", "severe", "rubber", "replace"),
    ],
)
def test_repair_replace_rules(
    damage_type, severity, material, expected
):
    assert choose_action(
        damage_type, severity, material
    ) == expected


def test_unknown_damage_type_raises_error():
    with pytest.raises(ValueError):
        choose_action("unknown_damage", "minor", "metal")


# --------------------------------------------------
# 2. ALL EIGHT METAL DEPRECIATION AGE BANDS
# --------------------------------------------------

@pytest.mark.parametrize(
    "vehicle_age, expected_percentage",
    [
        (0.25, 0),
        (0.75, 5),
        (1.5, 10),
        (2.5, 15),
        (3.5, 25),
        (4.5, 35),
        (7.0, 40),
        (11.0, 50),
    ],
)
def test_all_metal_depreciation_bands(
    vehicle_age, expected_percentage, rules
):
    assert get_metal_depreciation(
        vehicle_age, rules
    ) == expected_percentage


def test_metal_depreciation_at_ten_years(rules):
    # The configured bands currently treat 10 as the start
    # of the final band because their upper limits are exclusive.
    assert get_metal_depreciation(10, rules) == 50


# --------------------------------------------------
# 3. MATERIAL DEPRECIATION RULES
# --------------------------------------------------

@pytest.mark.parametrize(
    "material, expected_percentage",
    [
        ("plastic", 50),
        ("rubber", 50),
        ("nylon", 50),
        ("tyre", 50),
        ("battery", 50),
        ("fibreglass", 30),
        ("glass", 0),
        ("metal", 10),
        ("steel", 10),
        ("aluminium", 10),
    ],
)
def test_material_depreciation(
    material, expected_percentage, rules
):
    assert get_depreciation_pct(
        material, 1.5, rules
    ) == expected_percentage


def test_tire_spelling_aliases(rules):
    assert get_depreciation_pct("tire", 1, rules) == 50
    assert get_depreciation_pct("tires", 1, rules) == 50
    assert get_depreciation_pct("tyres", 1, rules) == 50


def test_fiberglass_spelling_alias(rules):
    assert get_depreciation_pct(
        "fiberglass", 1, rules
    ) == 30


def test_unknown_material_has_no_depreciation_rule(rules):
    assert get_depreciation_pct(
        "unknown_material", 1, rules
    ) is None


# --------------------------------------------------
# 4. DEPRECIATION CONFIGURATION VALIDATION
# --------------------------------------------------

def test_depreciation_configuration_has_eight_metal_bands(rules):
    assert len(rules["metal_age_bands"]) == 8


def test_paint_depreciation_applies_to_material_component(rules):
    painting = rules["painting_rule"]

    assert painting["depreciation_pct"] == 50
    assert painting["applies_to"] == "paint_material_cost_only"


def test_paint_material_fraction_is_within_valid_range(rules):
    fraction = float(
        rules["painting_rule"][
            "consolidated_paint_bill_material_fraction"
        ]
    )

    assert 0 <= fraction <= 1


def test_price_lookup_accepts_annotated_year_range():
    from cost_engine import find_part_price

    vehicle = {"make": "Maruti Suzuki", "model": "Swift", "year": 2021}
    row = {
        "make": "Maruti Suzuki",
        "model": "Swift",
        "year_range": "2017-2021 - compatibility to verify",
        "part": "right_headlamp",
        "material": "plastic",
        "part_price_inr": "2999",
        "paint_cost_inr": "",
        "source_url": "test-source",
        "date_accessed": "2026-10-09",
    }
    assert find_part_price(vehicle, "right_headlamp", [row]) == row
