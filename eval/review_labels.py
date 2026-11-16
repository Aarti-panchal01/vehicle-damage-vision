"""Review page for the drafted eval labels: check each photo, fix its damages, click Approve.

Approving an image writes it back to data/cardd_eval/labels.json with
labeled_by "aarti_verified" and verified_by_human true. Only approved labels
should be used for numbers in the report.

Run from the repo root:
    streamlit run eval/review_labels.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.vision.vocab import DAMAGE_TYPES, PARTS, QUALITY_ISSUES, SEVERITIES

LABELS_PATH = REPO_ROOT / "data" / "cardd_eval" / "labels.json"
VERIFIED_BY = "aarti_verified"
DAMAGE_FIELDS = ("part", "damage_type", "severity")
VOCAB = {"part": PARTS, "damage_type": DAMAGE_TYPES, "severity": SEVERITIES}


def load_labels(path: Path = LABELS_PATH) -> dict:
    """Read labels.json."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_labels(labels: dict, path: Path = LABELS_PATH) -> None:
    """Write labels.json through a temp file, so a crash never leaves half a file."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(labels, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def clean_damages(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Drop fully empty rows and check the rest. Returns (damages, problems)."""
    damages, problems, seen = [], [], set()
    for number, row in enumerate(rows, start=1):
        values = {field: (row.get(field) or "").strip() for field in DAMAGE_FIELDS}
        if not any(values.values()):
            continue
        for field, value in values.items():
            if value not in VOCAB[field]:
                problems.append(f"Row {number}: {field} is {value or 'empty'}")
        key = (values["part"], values["damage_type"])
        if key in seen:
            problems.append(f"Row {number}: {key[0]} / {key[1]} is listed twice")
        seen.add(key)
        damages.append(values)
    return damages, problems


def approve_item(labels: dict, image_id: str, damages: list[dict], flags: list[str], notes: str) -> dict:
    """Store the reviewed damages, flags and notes for one image and mark it verified."""
    for item in labels["items"]:
        if item["image_id"] == image_id:
            item["damages"] = damages
            item["image_quality_flags"] = flags
            item["label_notes"] = notes
            item["labeled_by"] = VERIFIED_BY
            item["verified_by_human"] = True
            return labels
    raise KeyError(image_id)


def main() -> None:
    import pandas as pd
    import streamlit as st

    st.set_page_config(page_title="Label review", page_icon="🏷️", layout="wide")
    labels = load_labels()

    with st.sidebar:
        splits = st.multiselect("Splits", ["eval", "dev"], default=["eval"])
        items = [item for item in labels["items"] if item["split"] in splits]
        if not items:
            st.stop()
        done = sum(item["labeled_by"] == VERIFIED_BY for item in items)
        st.progress(done / len(items), text=f"{done} / {len(items)} approved")
        ids = [item["image_id"] for item in items]
        if "index" not in st.session_state or st.session_state.index >= len(ids):
            st.session_state.index = 0
        st.radio(
            "Image",
            range(len(ids)),
            key="index",
            format_func=lambda i: f"{'✅' if items[i]['labeled_by'] == VERIFIED_BY else '⬜'} {ids[i]}",
        )
        st.caption(labels["left_right_convention"])

    item = items[st.session_state.index]
    st.title(item["image_id"])
    st.caption(
        f"Category: {item['category']} · CarDD classes: {', '.join(item['cardd_classes']) or 'none'}"
        f" · degradation: {item['degradation'] or 'none'} · labeled by: {item['labeled_by']}"
    )

    left, right = st.columns([3, 2])
    with left:
        st.image(str(REPO_ROOT / "data" / "cardd_eval" / item["file"]), use_container_width=True)
    with right:
        st.subheader("Damages")
        table = pd.DataFrame(item["damages"], columns=list(DAMAGE_FIELDS))
        edited = st.data_editor(
            table,
            key=f"damages_{item['image_id']}",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                field: st.column_config.SelectboxColumn(field, options=list(VOCAB[field]), required=True)
                for field in DAMAGE_FIELDS
            },
        )
        st.caption("Add a row with + at the bottom. Delete a row by selecting it and pressing Delete.")
        flag_options = [f"image_0_{issue}" for issue in QUALITY_ISSUES]
        flags = st.multiselect(
            "Image quality flags",
            flag_options,
            default=[f for f in item["image_quality_flags"] if f in flag_options],
            key=f"flags_{item['image_id']}",
        )
        notes = st.text_area("Notes", item.get("label_notes", ""), key=f"notes_{item['image_id']}")

        rows = edited.where(pd.notna(edited), None).to_dict("records")
        damages, problems = clean_damages(rows)
        for problem in problems:
            st.error(problem)
        def on_approve() -> None:
            save_labels(approve_item(load_labels(), item["image_id"], damages, flags, notes))
            if st.session_state.index < len(ids) - 1:
                st.session_state.index += 1

        st.button("Approve", type="primary", disabled=bool(problems), use_container_width=True, on_click=on_approve)


if __name__ == "__main__":
    main()
