import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
PRICE_DIR = BASE_DIR / "data" / "prices"
PARTS_FILE = PRICE_DIR / "parts_prices.csv"
LABOUR_FILE = PRICE_DIR / "labour_rates.csv"
PAINT_FILE = PRICE_DIR / "paint_rates.csv"
DEPRECIATION_FILE = PRICE_DIR / "depreciation_rules.json"

PART_ALIASES = {
    "bonnet": ("bonnet_hood", "bonnet"),
    "boot_lid": ("boot_lid", "dicky"),
    "left_headlamp": ("left_headlamp", "headlamp"),
    "right_headlamp": ("right_headlamp", "headlamp"),
    "left_taillamp": ("left_tail_lamp", "tail_lamp"),
    "right_taillamp": ("right_tail_lamp", "tail_lamp"),
    "left_orvm": ("left_outside_mirror", "outside_mirror"),
    "right_orvm": ("right_outside_mirror", "outside_mirror"),
    "front_left_door": ("front_left_door", "front_door"),
    "front_right_door": ("front_right_door", "front_door"),
    "rear_left_door": ("rear_left_door", "rear_door"),
    "rear_right_door": ("rear_right_door", "rear_door"),
    "front_left_fender": ("front_left_fender", "front_fender"),
    "front_right_fender": ("front_right_fender", "front_fender", "front_fender_right"),
    "front_left_tyre": ("front_left_tyre", "tyre"),
    "front_right_tyre": ("front_right_tyre", "tyre"),
    "rear_left_tyre": ("rear_left_tyre", "tyre"),
    "rear_right_tyre": ("rear_right_tyre", "tyre"),
}

SEVERITY_RANK = {"minor": 1, "moderate": 2, "severe": 3}
VALID_DAMAGE_TYPES = {
    "dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"
}
VALID_SEVERITIES = set(SEVERITY_RANK)
VALID_PARTS = {
    "front_bumper", "rear_bumper", "bonnet", "boot_lid", "grille", "roof",
    "windshield", "rear_windshield", "left_headlamp", "right_headlamp",
    "left_taillamp", "right_taillamp", "left_orvm", "right_orvm",
    "front_left_door", "front_right_door", "rear_left_door", "rear_right_door",
    "front_left_fender", "front_right_fender", "left_quarter_panel",
    "right_quarter_panel", "front_left_tyre", "front_right_tyre",
    "rear_left_tyre", "rear_right_tyre",
}


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_depreciation_rules():
    with open(DEPRECIATION_FILE, "r", encoding="utf-8-sig") as file:
        rules = json.load(file)
    if not isinstance(rules.get("rules"), list):
        raise ValueError("Depreciation rules must contain a rules list.")
    if not isinstance(rules.get("metal_age_bands"), list):
        raise ValueError("Depreciation rules must contain metal_age_bands.")
    painting = rules.get("painting_rule", {})
    pct = float(painting.get("depreciation_pct", 50))
    fraction = float(painting.get("consolidated_paint_bill_material_fraction", 0.25))
    if not 0 <= pct <= 100 or not 0 <= fraction <= 1:
        raise ValueError("Invalid painting depreciation configuration.")
    return rules


def get_vehicle_age(vehicle_year, reference_year=None):
    reference_year = reference_year or date.today().year
    year = int(vehicle_year)
    if year < 1980 or year > reference_year + 1:
        raise ValueError(f"Invalid vehicle year: {year}")
    return max(0, reference_year - year)


def get_metal_depreciation(age, rules=None):
    rules = rules or load_depreciation_rules()
    for band in rules["metal_age_bands"]:
        low = float(band["min_age_years"])
        high = band.get("max_age_years")
        if age >= low and (high is None or age < float(high)):
            return float(band["depreciation_pct"])
    raise ValueError(f"No metal depreciation band matches age {age}.")


def get_depreciation_pct(material, vehicle_age, rules):
    material = material.strip().lower()
    if material in ("metal", "steel", "aluminium", "aluminum"):
        return get_metal_depreciation(vehicle_age, rules)
    aliases = {"tyres": "tyre", "tire": "tyre", "tires": "tyre",
               "fiberglass": "fibreglass"}
    material = aliases.get(material, material)
    for rule in rules["rules"]:
        if rule["material"].strip().lower() == material:
            return float(rule["depreciation_pct"])
    return None


def choose_action(damage_type, severity, material):
    damage_type = str(damage_type).strip().lower()
    severity = str(severity).strip().lower()
    material = str(material).strip().lower()
    if damage_type not in VALID_DAMAGE_TYPES:
        raise ValueError(f"Unsupported damage type: {damage_type}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"Unsupported severity: {severity}")
    if damage_type in ("lamp_broken", "glass_shatter"):
        return "replace"
    if damage_type == "scratch":
        return "repair"
    if damage_type == "dent":
        return "replace" if severity == "severe" else "repair"
    if damage_type == "crack":
        return "replace" if material in ("plastic", "fibreglass", "fiberglass") and severity == "severe" else "repair"
    if damage_type == "tire_flat":
        return "replace" if severity == "severe" else "repair"
    raise ValueError(f"Unsupported damage type: {damage_type}")


def _candidate_parts(part):
    return (part,) + PART_ALIASES.get(part, ())


def find_part_price(vehicle, part, prices):
    make = vehicle["make"].strip().lower()
    model = vehicle["model"].strip().lower()
    year = int(vehicle["year"])
    candidates = {x.lower() for x in _candidate_parts(part)}
    matches = []
    for row in prices:
        if row.get("make", "").strip().lower() != make:
            continue
        if row.get("model", "").strip().lower() != model:
            continue
        if row.get("part", "").strip().lower() not in candidates:
            continue
        try:
            # Accept annotated source ranges such as
            # "2017-2021 - compatibility to verify" while preserving the
            # note in the source CSV for manual compatibility review.
            year_tokens = re.findall(r"\d{4}", row["year_range"])
            if len(year_tokens) >= 2:
                start, end = int(year_tokens[0]), int(year_tokens[1])
                if start <= year <= end:
                    matches.append(row)
        except (ValueError, AttributeError, KeyError):
            continue
    if len(matches) > 1:
        raise ValueError(f"Multiple price records match {make} {model} {year} {part}")
    return matches[0] if matches else None


def _matching_labour_rows(model, part, action, rates):
    aliases = _candidate_parts(part)
    services = {f"{p}_{action}_labour".lower() for p in aliases}
    matches = []
    for row in rates:
        if row.get("service", "").strip().lower() not in services:
            continue
        if row.get("includes_paint_material", "no").strip().lower() in ("yes", "true", "1"):
            continue
        rate_model = row.get("vehicle_model", "").strip().lower()
        if rate_model not in ("all", model.strip().lower()):
            continue
        # The engine needs a fixed job/panel rate; hourly quotes need a
        # documented duration before they can be compared.
        if row.get("rate_unit", "per_job").strip().lower() not in ("per_job", "per_panel", "per_part"):
            continue
        try:
            rate = float(row["rate_inr"])
            if rate < 0:
                continue
            matches.append((rate, row))
        except (ValueError, TypeError, KeyError):
            continue
    return matches


def get_labour_cost(model, part, action, rates):
    """Return the median of comparable garage rates, or None if unavailable."""
    matches = _matching_labour_rows(model, part, action, rates)
    if not matches:
        return None
    values = sorted(rate for rate, _ in matches)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def get_labour_sources(model, part, action, rates):
    """Return source labels for every comparable garage rate used."""
    matches = _matching_labour_rows(model, part, action, rates)
    labels = []
    for _, row in matches:
        label = row.get("source", "").strip() or row.get("garage_name", "").strip()
        date_accessed = row.get("date_accessed", "").strip()
        if date_accessed:
            label = f"{label} (accessed {date_accessed})"
        if label:
            labels.append(label)
    return labels


def _matching_paint_rows(model, part, rates):
    aliases = _candidate_parts(part)
    part_services = {f"{p}_painting".lower() for p in aliases}
    part_services.update(f"{p}_paint".lower() for p in aliases)
    generic_services = {"full_panel_painting", "panel_painting"}
    matches = []
    for row in rates:
        service = row.get("service", "").strip().lower()
        if service not in part_services and service not in generic_services:
            continue
        if row.get("includes_paint_material", "no").strip().lower() not in ("yes", "true", "1"):
            continue
        rate_model = row.get("vehicle_model", "").strip().lower()
        if rate_model not in ("all", model.strip().lower()):
            continue
        if row.get("rate_unit", "per_panel").strip().lower() not in ("per_job", "per_panel", "per_part"):
            continue
        try:
            rate = float(row["rate_inr"])
            if rate < 0:
                continue
            matches.append((rate, row, service in part_services))
        except (ValueError, TypeError, KeyError):
            continue
    # Prefer a part-specific painting rate; use a generic full-panel rate only
    # when no part-specific quote exists.
    if any(specific for _, _, specific in matches):
        matches = [m for m in matches if m[2]]
    return matches


def get_paint_cost(model, part, rates):
    """Return median all-in painting quote (paint material included), or None."""
    matches = _matching_paint_rows(model, part, rates)
    if not matches:
        return None
    values = sorted(rate for rate, _, _ in matches)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def get_paint_sources(model, part, rates):
    matches = _matching_paint_rows(model, part, rates)
    labels = []
    for _, row, _ in matches:
        label = row.get("source", "").strip() or row.get("garage_name", "").strip()
        date_accessed = row.get("date_accessed", "").strip()
        if date_accessed:
            label = f"{label} (accessed {date_accessed})"
        if label:
            labels.append(label)
    return labels


def _validate_contract_a(contract_a):
    if not isinstance(contract_a, dict):
        raise ValueError("Contract A must be a JSON object.")
    if "error_code" in contract_a:
        raise ValueError("Received VisionError, not a successful Contract A report.")
    required = {"claim_id", "vehicle", "user_description", "damages", "image_quality_flags", "model_used", "prompt_strategy"}
    missing = required - set(contract_a)
    if missing:
        raise ValueError(f"Contract A is missing fields: {sorted(missing)}")
    if not isinstance(contract_a["claim_id"], str) or not contract_a["claim_id"].strip():
        raise ValueError("Contract A claim_id must be a non-empty string.")
    vehicle = contract_a["vehicle"]
    if not isinstance(vehicle, dict):
        raise ValueError("Contract A vehicle must be an object.")
    for field in ("make", "model", "year", "fuel"):
        if field not in vehicle:
            raise ValueError(f"Contract A vehicle is missing '{field}'.")
    for field in ("make", "model", "fuel"):
        if not isinstance(vehicle[field], str) or not vehicle[field].strip():
            raise ValueError(f"Contract A vehicle '{field}' must be a non-empty string.")
    if isinstance(vehicle["year"], bool) or not isinstance(vehicle["year"], int) or not 1980 <= vehicle["year"] <= 2100:
        raise ValueError("Contract A vehicle year must be an integer from 1980 to 2100.")
    for field in ("user_description", "model_used", "prompt_strategy"):
        if not isinstance(contract_a[field], str):
            raise ValueError(f"Contract A '{field}' must be a string.")
    if not isinstance(contract_a["image_quality_flags"], list) or not all(
        isinstance(flag, str) for flag in contract_a["image_quality_flags"]
    ):
        raise ValueError("Contract A image_quality_flags must be a list of strings.")
    if not isinstance(contract_a["damages"], list):
        raise ValueError("Contract A damages must be a list.")
    for index, damage in enumerate(contract_a["damages"]):
        if not isinstance(damage, dict):
            raise ValueError(f"Damage entry {index} must be an object.")
        for field in ("part", "damage_type", "severity", "confidence", "image_index"):
            if field not in damage:
                raise ValueError(f"Damage entry is missing '{field}'.")
        if not isinstance(damage["confidence"], (int, float)) or isinstance(damage["confidence"], bool) or not 0 <= damage["confidence"] <= 1:
            raise ValueError("Damage confidence must be a number from 0 to 1.")
        if not isinstance(damage["image_index"], int) or isinstance(damage["image_index"], bool) or damage["image_index"] < 0:
            raise ValueError("Damage image_index must be a non-negative integer.")
        if "notes" in damage and not isinstance(damage["notes"], str):
            raise ValueError("Damage notes must be a string.")
        if damage["part"] not in VALID_PARTS:
            raise ValueError(f"Unsupported part: {damage['part']}")
        if damage["damage_type"] not in VALID_DAMAGE_TYPES:
            raise ValueError(f"Unsupported damage type: {damage['damage_type']}")
        if damage["severity"] not in VALID_SEVERITIES:
            raise ValueError(f"Unsupported severity: {damage['severity']}")


def calculate_estimate(contract_a, reference_year=None):
    """Convert Contract A to Contract B. One cost line per physical part."""
    _validate_contract_a(contract_a)
    prices = read_csv(PARTS_FILE)
    rates = read_csv(LABOUR_FILE)
    paint_rates = read_csv(PAINT_FILE) if PAINT_FILE.exists() else []
    rules = load_depreciation_rules()
    vehicle = contract_a["vehicle"]
    age = get_vehicle_age(vehicle["year"], reference_year)

    grouped = defaultdict(list)
    for damage in contract_a["damages"]:
        grouped[damage["part"]].append(damage)

    line_items, unpriced_parts, warnings = [], [], []
    painting = rules.get("painting_rule", {})
    paint_fraction = float(painting.get("consolidated_paint_bill_material_fraction", 0.25))
    paint_depr_pct = float(painting.get("depreciation_pct", 50))

    for part, damages in sorted(grouped.items()):
        try:
            price_row = find_part_price(vehicle, part, prices)
        except ValueError as exc:
            warnings.append(str(exc))
            unpriced_parts.append(part)
            continue
        if price_row is None:
            warnings.append(f"{part}: no matching part price for {vehicle['make']} {vehicle['model']} {vehicle['year']}")
            unpriced_parts.append(part)
            continue

        material = price_row.get("material", "").strip().lower()
        if not material or material == "unknown":
            warnings.append(f"{part}: material is unknown in the price database")
            unpriced_parts.append(part)
            continue

        decisions = [choose_action(d["damage_type"], d["severity"], material) for d in damages]
        # Replacement dominates repair for the same physical part, preventing duplicate part charges.
        action = "replace" if "replace" in decisions else "repair"
        damage_types = sorted({d["damage_type"] for d in damages})

        labour = get_labour_cost(vehicle["model"], part, action, rates)
        labour_sources = get_labour_sources(vehicle["model"], part, action, rates)
        if labour is None:
            warnings.append(f"{part}: missing labour rate for {part}_{action}_labour")
            unpriced_parts.append(part)
            continue

        # Part cost applies only when replacing the physical part.
        try:
            replacement_price = float(price_row.get("part_price_inr") or "")
            if replacement_price < 0:
                raise ValueError
        except (ValueError, TypeError):
            if action == "replace":
                warnings.append(f"{part}: replacement part price is missing or invalid")
                unpriced_parts.append(part)
                continue
            replacement_price = 0.0

        part_cost = replacement_price if action == "replace" else 0.0

        # The source dataset has no paint price in most rows. Never silently treat
        # a missing paint rate as a verified free service.
        requires_paint = any(t in ("dent", "scratch", "crack") for t in damage_types)
        raw_paint = price_row.get("paint_cost_inr", "").strip()
        paint_sources = []
        if requires_paint and raw_paint == "":
            paint_cost = get_paint_cost(vehicle["model"], part, paint_rates)
            paint_sources = get_paint_sources(vehicle["model"], part, paint_rates)
            if paint_cost is None:
                warnings.append(f"{part}: paint cost is missing or no all-in paint quote includes material")
                unpriced_parts.append(part)
                continue
        else:
            try:
                paint_cost = float(raw_paint) if requires_paint else 0.0
                if paint_cost < 0:
                    raise ValueError
            except ValueError:
                warnings.append(f"{part}: paint cost is invalid")
                unpriced_parts.append(part)
                continue

        depreciation_pct = get_depreciation_pct(material, age, rules)
        if depreciation_pct is None:
            warnings.append(f"{part}: no depreciation rule for material '{material}'")
            unpriced_parts.append(part)
            continue

        part_depreciation = part_cost * depreciation_pct / 100
        paint_depreciation = paint_cost * paint_fraction * paint_depr_pct / 100
        depreciation_amount = part_depreciation + paint_depreciation
        gross = part_cost + labour + paint_cost
        claimable = max(0.0, gross - depreciation_amount)

        line_items.append({
            "part": part,
            "action": action,
            "material": material,
            "part_cost": round(part_cost, 2),
            "labour_cost": round(labour, 2),
            "paint_cost": round(paint_cost, 2),
            "depreciation_pct": depreciation_pct,
            "depreciation_amount": round(depreciation_amount, 2),
            "claimable_amount": round(claimable, 2),
            "price_source": "; ".join(
                [f"Part: {price_row.get('source_url', '')}, accessed {price_row.get('date_accessed', '')}"]
                + ([f"Labour: {source}" for source in labour_sources] if labour_sources else [])
                + ([f"Painting: {source}" for source in paint_sources] if paint_sources else [])
            )
        })

    totals = {
        "gross": round(sum(i["part_cost"] + i["labour_cost"] + i["paint_cost"] for i in line_items), 2),
        "depreciation": round(sum(i["depreciation_amount"] for i in line_items), 2),
        "claimable": round(sum(i["claimable_amount"] for i in line_items), 2)
    }
    for warning in warnings:
        print(f"COST ENGINE WARNING: {warning}")

    return {
        "claim_id": contract_a["claim_id"],
        "currency": "INR",
        "vehicle_age_years": age,
        "line_items": line_items,
        "totals": totals,
        "unpriced_parts": sorted(set(unpriced_parts))
    }


if __name__ == "__main__":
    input_file = BASE_DIR / "mocks" / "contract_a_demo.json"
    with open(input_file, "r", encoding="utf-8-sig") as file:
        report = json.load(file)
    print(json.dumps(calculate_estimate(report), indent=2))
