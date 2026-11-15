"""Draw the evaluation charts from eval/results/summary.csv into eval/results/*.png.

Usage:
    python -m eval.make_charts
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "eval" / "results"

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
CONNECTOR = "#b9b8b2"

PANELS = [
    ("json_valid_first_try", "JSON valid on first try", "{:.0%}", 1.0),
    ("damage_type_f1", "Damage type F1", "{:.2f}", 1.0),
    ("part_type_pair_f1", "Part + type pair F1", "{:.2f}", 1.0),
    ("severity_accuracy", "Severity accuracy (matched parts)", "{:.2f}", 1.0),
    ("avg_latency_s", "Avg latency per photo (s)", "{:.1f}", None),
    ("avg_cost_usd", "Cost per 1,000 photos (USD, paid-tier list price)", "{:.2f}", None),
]


def load_summary(path: Path = RESULTS_DIR / "summary.csv") -> list[dict]:
    """Rows of summary.csv, numbers converted to float where possible."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key, value in row.items():
            try:
                row[key] = float(value)
            except (TypeError, ValueError):
                pass
    return rows


def style_axis(ax) -> None:
    """Recessive grid and axes on the chart surface."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, length=0, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def label_for(row: dict) -> str:
    """Short y-axis label such as 'Gemini v1 +schema'."""
    provider = "Gemini" if row["provider"] == "gemini" else "Qwen"
    version = row["prompt_id"].split("_")[0]
    schema = " +schema" if str(row["enforce_schema"]) == "True" else ""
    return f"{provider} {version}{schema}"


def draw_part_f1(rows: list[dict], out: Path) -> None:
    """Dumbbell chart: exact part F1 vs corner-free part F1 per configuration."""
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * len(rows) + 1.6), facecolor=SURFACE)
    style_axis(ax)
    labels = [label_for(r) for r in rows]
    positions = list(range(len(rows)))[::-1]
    for y, row in zip(positions, rows):
        ax.plot([row["part_f1"], row["part_f1_corner_free"]], [y, y], color=CONNECTOR, linewidth=2, zorder=1)
    ax.scatter([r["part_f1"] for r in rows], positions, s=70, color=SERIES_1, edgecolors=SURFACE,
               linewidths=2, zorder=2, label="Exact part name")
    ax.scatter([r["part_f1_corner_free"] for r in rows], positions, s=70, color=SERIES_2, edgecolors=SURFACE,
               linewidths=2, zorder=2, label="Ignoring left/right/front/rear")
    top = rows[0]
    ax.annotate(f"{top['part_f1']:.2f}", (top["part_f1"], positions[0]), textcoords="offset points",
                xytext=(0, 9), ha="center", fontsize=8, color=TEXT_SECONDARY)
    ax.annotate(f"{top['part_f1_corner_free']:.2f}", (top["part_f1_corner_free"], positions[0]),
                textcoords="offset points", xytext=(0, 9), ha="center", fontsize=8, color=TEXT_SECONDARY)
    ax.set_yticks(positions, labels, color=TEXT_PRIMARY)
    ax.set_xlim(0, 1.02)
    ax.set_xlabel("Part-level F1 on 20 eval photos", color=TEXT_SECONDARY, fontsize=9)
    ax.set_title("Most part errors are the wrong side, not the wrong part", loc="left",
                 color=TEXT_PRIMARY, fontsize=11, pad=24)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8,
              labelcolor=TEXT_SECONDARY, handletextpad=0.3, borderaxespad=0.2)
    fig.tight_layout()
    fig.savefig(out, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def draw_metric_panels(rows: list[dict], out: Path) -> None:
    """Small multiples, one panel per metric, one bar per configuration."""
    fig, axes = plt.subplots(2, 3, figsize=(12, 0.32 * len(rows) * 2 + 2.4), facecolor=SURFACE)
    labels = [label_for(r) for r in rows]
    positions = list(range(len(rows)))[::-1]
    for ax, (key, title, fmt, x_max) in zip(axes.flat, PANELS):
        style_axis(ax)
        values = []
        for row in rows:
            value = row.get(key)
            if key == "avg_cost_usd" and isinstance(value, float):
                value = value * 1000
            values.append(value if isinstance(value, float) else 0.0)
        ax.barh(positions, values, height=0.6, color=SERIES_1, edgecolor=SURFACE, linewidth=2)
        limit = x_max or max(values) * 1.25 or 1
        for y, value in zip(positions, values):
            ax.text(value + limit * 0.015, y, fmt.format(value), va="center", fontsize=8, color=TEXT_SECONDARY)
        ax.set_xlim(0, limit * (1.12 if x_max else 1))
        ax.set_yticks(positions, labels if ax in axes[:, 0] else [""] * len(labels), color=TEXT_PRIMARY)
        ax.set_title(title, loc="left", color=TEXT_PRIMARY, fontsize=10)
    fig.suptitle("Prompt versions on 20 eval photos", x=0.01, ha="left", color=TEXT_PRIMARY, fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main() -> int:
    rows = load_summary()
    draw_part_f1(rows, RESULTS_DIR / "part_f1_exact_vs_corner_free.png")
    draw_metric_panels(rows, RESULTS_DIR / "metrics_by_config.png")
    print(f"wrote charts for {len(rows)} configurations to {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
