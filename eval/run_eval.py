"""Run every prompt configuration on the evaluation images and write results to eval/results/.

API replies are cached in eval/cache/, so a rerun with the same prompts and
images makes no API calls and costs nothing.

Usage:
    python -m eval.run_eval                       # every configuration
    python -m eval.run_eval --configs gemini_v1 groq_v1
    python -m eval.run_eval --providers groq --limit 3
"""

from __future__ import annotations 

import argparse
import csv
import json
import sys
from dataclasses import dataclass 
from pathlib import Path

from dotenv import load_dotenv 

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.metrics import ImageOutcome, summarise # noqa: E402
from src.vision.assess import assess_damage # noqa: E402
from src.vision.providers import make_provider # noqa: E402
from src.vision.providers.base import ImageInput # noqa: E402
from src.vision.providers.cache import CachedProvider # noqa: E402

LABELS_PATH = REPO_ROOT / "data" / "cardd_eval" / "labels.json"
IMAGES_DIR = REPO_ROOT / "data" / "cardd_eval" / "images"
RESULTS_DIR = REPO_ROOT / "eval" / "results"
CACHE_DIR = REPO_ROOT / "eval" / "cache"
FEW_SHOT_EXAMPLE_IDS = {"dev_03", "dev_10"}
EVAL_VEHICLE = {"make": "unknown", "model": "unknown", "year": 2020, "fuel": "petrol"}

PRICES_USD_PER_MILLION = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.8-flash": (0.75, 3.75),
    "qwen/qwen3.8-27b": (0.80, 4.00),
}


@dataclass(frozen=True)
class EvalConfig:
    """One row of the comparison: a provider, a prompt version and whether API schema enforcement is on."""

    name: str
    provider: str
    prompt_id: str
    enforce_schema: bool = False


CONFIGS: list[EvalConfig] = [
    EvalConfig("gemini_v0", "gemini", "v0_baseline"),
    EvalConfig("gemini_v1", "gemini", "v1_structured"),
    EvalConfig("gemini_v1_schema", "gemini", "v1_structured", True),
    EvalConfig("gemini_v2", "gemini", "v2_fewshot"),
    EvalConfig("gemini_v3", "gemini", "v3_cot"),
    EvalConfig("groq_v0", "groq", "v0_baseline"),
    EvalConfig("groq_v1", "groq", "v1_structured"),
    EvalConfig("groq_v1_schema", "groq", "v1_structured", True),
    EvalConfig("groq_v2", "groq", "v2_fewshot"),
    EvalConfig("groq_v3", "groq", "v3_cot"),
]

V4_CONFIGS: list[EvalConfig] = [
    EvalConfig("gemini_v4", "gemini", "v4_best"),
    EvalConfig("groq_v4", "groq", "v4_best"),
]


def available_configs() -> list[EvalConfig]:
    """All configurations whose prompt file exists on disk."""
    prompt_dir = REPO_ROOT / "prompts" / "vision"
    return [c for c in CONFIGS + V4_CONFIGS if (prompt_dir / f"{c.prompt_id}.md").exists()]


def load_eval_items(split: str) -> list[dict]:
    """Labelled items of one split from labels.json."""
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    return [
        item for item in labels["items"] if item["split"] == split and item["image_id"] not in FEW_SHOT_EXAMPLE_IDS
    ]


def run_config(config: EvalConfig, items: list[dict], providers: dict) -> tuple[list[ImageOutcome], list[dict], bool]:
    """Assess every item with one configuration. Returns outcomes, raw records and whether quota ran out."""
    provider = providers[config.provider]
    outcomes: list[ImageOutcome] = []
    records: list[dict] = []
    for item in items:
        image = ImageInput((IMAGES_DIR / f"{item['image_id']}.jpg").read_bytes())
        result = assess_damage(
            [image],
            EVAL_VEHICLE,
            provider,
            user_description="",
            prompt_id=config.prompt_id,
            enforce_schema=config.enforce_schema,
            claim_id="CLM-20261008-000",
        )
        if result.error is not None and result.error.error_code == "quota_exhausted":
            print(f"  quota exhausted on {config.provider} at {item['image_id']}; stopping this provider")
            return outcomes, records, True
        predicted = [d.model_dump() for d in result.report.damages] if result.ok else None
        flags = list(result.report.image_quality_flags) if result.ok else []
        outcomes.append(
            ImageOutcome(
                image_id=item["image_id"],
                category=item["category"],
                expected_damages=item["damages"],
                expected_flags=item["image_quality_flags"],
                predicted_damages=predicted,
                predicted_flags=flags,
                first_try_valid=result.first_try_valid,
                final_valid=result.ok,
                retries_used=result.retries_used,
                latency_s=result.latency_s,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        )
        records.append(
            {
                "config": config.name,
                "image_id": item["image_id"],
                "category": item["category"],
                "ok": result.ok,
                "first_try_valid": result.first_try_valid,
                "retries_used": result.retries_used,
                "predicted_damages": predicted,
                "predicted_flags": flags,
                "expected_damages": item["damages"],
                "error": result.error.model_dump() if result.error else None,
                "attempts": [
                    {"kind": a.kind, "valid": a.valid, "error": a.error, "text": a.reply.text,
                     "from_cache": a.reply.from_cache}
                    for a in result.attempts
                ],
            }
        )
        status = "ok" if result.ok else (result.error.error_code if result.error else "?")
        cached = all(a.reply.from_cache for a in result.attempts) if result.attempts else False
        print(f"  {config.name} {item['image_id']}: {status}{' (cached)' if cached else ''}", flush=True)
    return outcomes, records, False


def merge_rows(path: Path, new_rows: list[dict], replaced_configs: set[str]) -> list[dict]:
    """Keep rows from an earlier run for configurations that were not re-run this time."""
    if not path.exists():
        return new_rows
    with open(path, newline="", encoding="utf-8") as handle:
        old_rows = [row for row in csv.DictReader(handle) if row["config"] not in replaced_configs]
    order = {c.name: i for i, c in enumerate(CONFIGS + V4_CONFIGS)}
    return sorted(old_rows + new_rows, key=lambda row: order.get(row["config"], len(order)))


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write rows to a CSV file with the columns of the first row."""
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(summaries: list[dict], per_image_rows: list[dict], records_by_config: dict, results_dir: Path) -> None:
    """Update summary.csv and per_image.csv, and write one predictions JSONL per configuration run."""
    results_dir.mkdir(parents=True, exist_ok=True)
    completed = {row["config"] for row in summaries}
    write_csv(results_dir / "summary.csv", merge_rows(results_dir / "summary.csv", summaries, completed))
    write_csv(results_dir / "per_image.csv", merge_rows(results_dir / "per_image.csv", per_image_rows, completed))
    predictions_dir = results_dir / "predictions"
    predictions_dir.mkdir(exist_ok=True)
    for name, records in records_by_config.items():
        with open(predictions_dir / f"{name}.jsonl", "w", encoding="utf-8") as handle:
            handle.writelines(json.dumps(record) + "\n" for record in records)


def per_image_row(config: EvalConfig, outcome: ImageOutcome) -> dict:
    """One CSV row comparing expected and predicted parts for an image."""
    expected = sorted({d["part"] for d in outcome.expected_damages})
    predicted = sorted({d["part"] for d in outcome.predicted_damages or []})
    return {
        "config": config.name,
        "image_id": outcome.image_id,
        "category": outcome.category,
        "final_valid": outcome.final_valid,
        "expected_parts": ";".join(expected),
        "predicted_parts": ";".join(predicted) if outcome.predicted_damages is not None else "INVALID",
        "missed_parts": ";".join(sorted(set(expected) - set(predicted))),
        "extra_parts": ";".join(sorted(set(predicted) - set(expected))),
        "latency_s": outcome.latency_s,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Role 1 prompt evaluation")
    parser.add_argument("--configs", nargs="*", help="configuration names to run (default: all available)")
    parser.add_argument("--providers", nargs="*", choices=["gemini", "groq"], help="limit to these providers")
    parser.add_argument("--split", default="eval", choices=["eval", "dev"])
    parser.add_argument("--limit", type=int, default=None, help="only the first N images (for quick checks)")
    args = parser.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    configs = available_configs()
    if args.configs:
        configs = [c for c in configs if c.name in args.configs]
    if args.providers:
        configs = [c for c in configs if c.provider in args.providers]
    items = load_eval_items(args.split)[: args.limit]

    providers = {
        name: CachedProvider(make_provider(name), CACHE_DIR / name) for name in sorted({c.provider for c in configs})
    }
    summaries, per_image_rows, records_by_config = [], [], {}
    exhausted: set[str] = set()
    for config in configs:
        if config.provider in exhausted:
            print(f"skipping {config.name}: {config.provider} quota exhausted")
            continue
        print(f"running {config.name} on {len(items)} {args.split} images", flush=True)
        outcomes, records, quota_hit = run_config(config, items, providers)
        records_by_config[config.name] = records
        if quota_hit:
            exhausted.add(config.provider)
        if len(outcomes) < len(items):
            print(f"  {config.name} incomplete ({len(outcomes)}/{len(items)}), left out of summary.csv")
            continue
        model = providers[config.provider].model
        summary = {"config": config.name, "provider": config.provider, "model": model,
                   "prompt_id": config.prompt_id, "enforce_schema": config.enforce_schema}
        summary.update(summarise(outcomes, PRICES_USD_PER_MILLION.get(model)))
        summaries.append(summary)
        per_image_rows.extend(per_image_row(config, outcome) for outcome in outcomes)

    results_dir = RESULTS_DIR if args.split == "eval" else RESULTS_DIR / "dev_check"
    write_outputs(summaries, per_image_rows, records_by_config, results_dir)
    print(f"wrote {len(summaries)} configuration summaries to {results_dir}")
    return 1 if exhausted else 0


if __name__ == "__main__":
    sys.exit(main())