"""Fixed vocabularies shared by every module (Contract A, team plan section 3)."""

from __future__ import annotations

DAMAGE_TYPES: tuple[str, ...] = (
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "lamp_broken",
    "tire_flat",
)

SEVERITIES: tuple[str, ...] = ("minor", "moderate", "severe")

PARTS: tuple[str, ...] = (
    "front_bumper",
    "rear_bumper",
    "bonnet",
    "boot_lid",
    "grille",
    "roof",
    "windshield",
    "rear_windshield",
    "left_headlamp",
    "right_headlamp",
    "left_taillamp",
    "right_taillamp",
    "left_orvm",
    "right_orvm",
    "front_left_door",
    "front_right_door",
    "rear_left_door",
    "rear_right_door",
    "front_left_fender",
    "front_right_fender",
    "left_quarter_panel",
    "right_quarter_panel",
    "front_left_tyre",
    "front_right_tyre",
    "rear_left_tyre",
    "rear_right_tyre",
)

QUALITY_ISSUES: tuple[str, ...] = (
    "blurry",
    "too_dark",
    "overexposed",
    "low_resolution",
    "too_far",
    "partial_view",
    "obstructed",
    "no_vehicle",
)

SEVERITY_RANK: dict[str, int] = {name: rank for rank, name in enumerate(SEVERITIES)}

SIDE_TOKENS: tuple[str, ...] = ("front_left_", "front_right_", "rear_left_", "rear_right_", "left_", "right_")


def part_family(part: str) -> str:
    """Return the part name with its left/right/front/rear corner removed.

    Used for side-agnostic scoring: "rear_left_tyre" and "front_right_tyre" both
    become "tyre", "left_headlamp" becomes "headlamp", "front_bumper" stays as is.
    """
    for token in SIDE_TOKENS:
        if part.startswith(token):
            return part.removeprefix(token)
    return part
