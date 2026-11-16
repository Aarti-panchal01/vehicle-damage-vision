"""Scoring functions for the prompt evaluation. Pure functions, no API calls."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean

from src.vision.vocab import SEVERITY_RANK, part_family


@dataclass
class Counts:
    """True positive, false positive and false negative counts for one matching rule."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, predicted: set, expected: set) -> None:
        self.tp += len(predicted & expected)
        self.fp += len(predicted - expected)
        self.fn += len(expected - predicted)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def part_set(damages: Iterable[dict]) -> set[str]:
    """Distinct part names in a damage list."""
    return {d["part"] for d in damages}


def family_set(damages: Iterable[dict]) -> set[str]:
    """Distinct part families (corner removed) in a damage list."""
    return {part_family(d["part"]) for d in damages}


def type_set(damages: Iterable[dict]) -> set[str]:
    """Distinct damage types in a damage list."""
    return {d["damage_type"] for d in damages}


def pair_set(damages: Iterable[dict]) -> set[tuple[str, str]]:
    """Distinct (part, damage_type) pairs in a damage list."""
    return {(d["part"], d["damage_type"]) for d in damages}


def worst_severity_by_part(damages: Iterable[dict]) -> dict[str, str]:
    """Most severe severity reported for each part."""
    worst: dict[str, str] = {}
    for d in damages:
        current = worst.get(d["part"])
        if current is None or SEVERITY_RANK[d["severity"]] > SEVERITY_RANK[current]:
            worst[d["part"]] = d["severity"]
    return worst


def severity_matches(predicted: list[dict], expected: list[dict]) -> list[tuple[str, str]]:
    """(predicted, expected) worst-severity pairs for every part found in both lists."""
    pred_worst = worst_severity_by_part(predicted)
    gold_worst = worst_severity_by_part(expected)
    return [(pred_worst[part], gold_worst[part]) for part in sorted(pred_worst.keys() & gold_worst.keys())]


def flag_issues(flags: Iterable[str]) -> set[str]:
    """Issue names from flags such as image_0_too_dark -> {'too_dark'}."""
    return {flag.split("_", 2)[2] for flag in flags if flag.count("_") >= 2}


@dataclass
class ImageOutcome:
    """What the evaluation needs to know about one image under one configuration."""

    image_id: str
    category: str
    expected_damages: list[dict]
    expected_flags: list[str]
    predicted_damages: list[dict] | None
    predicted_flags: list[str]
    first_try_valid: bool
    final_valid: bool
    retries_used: int
    latency_s: float
    input_tokens: int
    output_tokens: int


def summarise(outcomes: list[ImageOutcome], price_per_million: tuple[float, float] | None = None) -> dict:
    """Aggregate every metric reported in RESULTS.md for one configuration.

    An image whose output stayed invalid counts as predicting no damage, so it
    adds false negatives but no false positives.
    """
    strict, corner_free, types, pairs = Counts(), Counts(), Counts(), Counts()
    severity_pairs: list[tuple[str, str]] = []
    for outcome in outcomes:
        predicted = outcome.predicted_damages or []
        strict.add(part_set(predicted), part_set(outcome.expected_damages))
        corner_free.add(family_set(predicted), family_set(outcome.expected_damages))
        types.add(type_set(predicted), type_set(outcome.expected_damages))
        pairs.add(pair_set(predicted), pair_set(outcome.expected_damages))
        severity_pairs.extend(severity_matches(predicted, outcome.expected_damages))

    no_damage = [o for o in outcomes if o.category == "no_damage"]
    degraded = [o for o in outcomes if o.category == "degraded"]
    clean_damaged = [o for o in outcomes if o.category == "damaged"]
    n = len(outcomes) or 1

    summary = {
        "images": len(outcomes),
        "json_valid_first_try": sum(o.first_try_valid for o in outcomes) / n,
        "json_valid_final": sum(o.final_valid for o in outcomes) / n,
        "avg_retries": sum(o.retries_used for o in outcomes) / n,
        "part_precision": strict.precision,
        "part_recall": strict.recall,
        "part_f1": strict.f1,
        "part_f1_corner_free": corner_free.f1,
        "damage_type_f1": types.f1,
        "part_type_pair_f1": pairs.f1,
        "severity_matched_parts": len(severity_pairs),
        "severity_accuracy": (
            sum(p == g for p, g in severity_pairs) / len(severity_pairs) if severity_pairs else None
        ),
        "severity_within_one": (
            sum(abs(SEVERITY_RANK[p] - SEVERITY_RANK[g]) <= 1 for p, g in severity_pairs) / len(severity_pairs)
            if severity_pairs
            else None
        ),
        "false_damage_rate_no_damage": (
            sum(bool(o.predicted_damages) for o in no_damage) / len(no_damage) if no_damage else None
        ),
        "quality_flag_hit_rate_degraded": (
            sum(bool(flag_issues(o.predicted_flags) & flag_issues(o.expected_flags)) for o in degraded) / len(degraded)
            if degraded
            else None
        ),
        "quality_flag_rate_clean": (
            sum(bool(o.predicted_flags) for o in clean_damaged) / len(clean_damaged) if clean_damaged else None
        ),
        "avg_latency_s": mean(o.latency_s for o in outcomes) if outcomes else 0.0,
        "avg_input_tokens": mean(o.input_tokens for o in outcomes) if outcomes else 0.0,
        "avg_output_tokens": mean(o.output_tokens for o in outcomes) if outcomes else 0.0,
    }
    if price_per_million is not None:
        input_price, output_price = price_per_million
        summary["avg_cost_usd"] = (
            summary["avg_input_tokens"] * input_price + summary["avg_output_tokens"] * output_price
        ) / 1_000_000
    else:
        summary["avg_cost_usd"] = None
    return summary
