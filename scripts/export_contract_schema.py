"""Write schemas/contract_a.schema.json from the Pydantic model, or check that it is current.

Usage:
    python -m scripts.export_contract_schema          # write the file
    python -m scripts.export_contract_schema --check  # exit 1 if the file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.vision.schema import contract_a_json_schema  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schemas" / "contract_a.schema.json"


def render() -> str:
    """Contract A JSON Schema as pretty-printed text."""
    return json.dumps(contract_a_json_schema(), indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = SCHEMA_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if SCHEMA_PATH.exists() else ""
        if current != text:
            print(f"{SCHEMA_PATH} is out of date; run python -m scripts.export_contract_schema")
            return 1
        print("Contract A schema file is up to date")
        return 0
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
