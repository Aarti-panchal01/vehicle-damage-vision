"""Generate mocks/contract_a_*.json from real vision-module runs on dev-split photos (plus one undamaged eval photo).

Usage:
    python -m scripts.make_mocks
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.vision import assess_damage, load_image, make_provider # noqa: E402
from src.vision.providers.cache import CachedProvider # noqa: E402

MOCKS_DIR = REPO_ROOT / "mocks"
IMAGES_DIR = REPO_ROOT / "data" / "cardd_eval" / "images"

CASES = [
    ("CLM-20261020-001", "dev_01", {"make": "Maruti Suzuki", "model": "Swift", "year": 2021, "fuel": "petrol"},
     "Scraped a parking pillar while turning out of the basement"),
    ("CLM-20261020-002", "eval_18", {"make": "Hyundai", "model": "Creta", "year": 2022, "fuel": "diesel"},
     "Heard a thud from the front while parking at the mall, not sure if anything is damaged"),
    ("CLM-20261020-003", "dev_04", {"make": "Tata", "model": "Nexon", "year": 2023, "fuel": "petrol"},
     "Windshield smashed by a falling branch during the storm"),
    ("CLM-20261020-004", "dev_05", {"make": "Honda", "model": "City", "year": 2019, "fuel": "petrol"},
     "Another car hit the driver side at a junction"),
    ("CLM-20261020-005", "dev_09", {"make": "Maruti Suzuki", "model": "Baleno", "year": 2020, "fuel": "cng"},
     "Bumper scraped in traffic, photo taken at night on my phone"),
]


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    provider = CachedProvider(make_provider("gemini"), REPO_ROOT / "eval" / "cache" / "gemini")
    MOCKS_DIR.mkdir(exist_ok=True)
    for claim_id, image_id, vehicle, description in CASES:
        result = assess_damage([load_image(IMAGES_DIR / f"{image_id}.jpg")], vehicle, provider, description,
                               claim_id=claim_id)
        payload = result.report.model_dump() if result.ok else result.error.model_dump()
        path = MOCKS_DIR / f"contract_a_{claim_id[-3:]}_{image_id}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: {'ok' if result.ok else result.error.error_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
