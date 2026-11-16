"""Generate Contract B integration outputs for the five Role 1 sample reports."""
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "cost"))
import cost_engine  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

INPUT_DIR = ROOT / "role1_mocks"
OUTPUT_DIR = ROOT / "outputs" / "role2_contract_b_samples"
REFERENCE_YEAR = 2026
SCHEMA_FILE = ROOT / "schemas" / "contract_b.schema.json"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    contract_b_schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    validator = Draft202012Validator(contract_b_schema)
    audit = {
        "reference_year": REFERENCE_YEAR,
        "contract_b_schema": str(SCHEMA_FILE.relative_to(ROOT)).replace("\\", "/"),
        "status_note": (
            "Integration outputs only. A sample with non-empty unpriced_parts "
            "is incomplete and must not be treated as a final repair estimate."
        ),
        "samples": [],
    }
    for input_path in sorted(INPUT_DIR.glob("contract_a_*.json")):
        contract_a = json.loads(input_path.read_text(encoding="utf-8"))
        warnings = io.StringIO()
        with contextlib.redirect_stdout(warnings):
            contract_b = cost_engine.calculate_estimate(
                contract_a, reference_year=REFERENCE_YEAR
            )
        validation_errors = sorted(validator.iter_errors(contract_b), key=lambda e: list(e.path))
        if validation_errors:
            details = "; ".join(error.message for error in validation_errors)
            raise ValueError(f"Generated Contract B failed schema validation for {input_path.name}: {details}")
        output_path = OUTPUT_DIR / input_path.name.replace(
            ".json", "_contract_b.json"
        )
        output_path.write_text(
            json.dumps(contract_b, indent=2) + "\n", encoding="utf-8"
        )
        audit["samples"].append({
            "input_file": input_path.name,
            "output_file": str(output_path.relative_to(ROOT)).replace("\\", "/"),
            "claim_id": contract_b["claim_id"],
            "damage_observations": len(contract_a["damages"]),
            "priced_line_items": len(contract_b["line_items"]),
            "contract_b_schema_valid": True,
            "unpriced_parts": contract_b["unpriced_parts"],
            "totals": contract_b["totals"],
            "warnings": [
                line.replace("COST ENGINE WARNING: ", "")
                for line in warnings.getvalue().splitlines()
            ],
        })
    (OUTPUT_DIR / "sample_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
