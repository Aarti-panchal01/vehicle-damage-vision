"""Role 1 demo: upload car photos, pick a prompt version, see Contract A and a readable summary.

Run from the repo root:
    streamlit run src/vision/demo_app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st # noqa: E402
from dotenv import load_dotenv # noqa: E402

from src.vision import ImageInput, assess_damage, make_provider # noqa: E402
from src.vision.assess import DEFAULT_PROMPT_ID, MAX_IMAGES # noqa: E402
from src.vision.prompts import list_prompt_versions # noqa: E402
from src.vision.providers import MockProvider # noqa: E402

SAMPLE_REPLY = json.dumps(
    {
        "damages": [
            {"part": "front_bumper", "damage_type": "dent", "severity": "moderate", "confidence": 0.8,
             "image_index": 0, "notes": "Offline sample: dent about 15 cm wide on the lower bumper"}
        ],
        "image_quality_flags": [],
    }
)
SEVERITY_BADGE = {"minor": "🟢 minor", "moderate": "🟠 moderate", "severe": "🔴 severe"}
ISSUE_TEXT = {
    "blurry": "is blurry",
    "too_dark": "is too dark",
    "overexposed": "is overexposed",
    "low_resolution": "is low resolution",
    "too_far": "was taken too far away",
    "partial_view": "shows only part of the car",
    "obstructed": "is blocked by something",
    "no_vehicle": "does not show a vehicle",
}


def build_provider(choice: str):
    """Create the selected provider, or an offline mock that needs no key."""
    if choice == "Offline sample (no API key)":
        return MockProvider([SAMPLE_REPLY] * 3)
    return make_provider("gemini" if choice.startswith("Gemini") else "groq")


def describe_flag(flag: str) -> str:
    """Turn image_1_blurry into 'Photo 1 is blurry'."""
    _, index, issue = flag.split("_", 2)
    return f"Photo {index} {ISSUE_TEXT.get(issue, issue.replace('_', ' '))}"


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    st.set_page_config(page_title="Damage assessment (Role 1)", page_icon="🚗", layout="wide")
    st.title("Vehicle damage assessment")
    st.caption("Role 1 vision module: photos in, Contract A damage report out. Prices are not estimated here.")

    with st.sidebar:
        st.header("Settings")
        provider_choice = st.selectbox(
            "Model", ["Gemini 3.5 Flash-Lite", "Qwen 3.8 27B (Groq)", "Offline sample (no API key)"]
        )
        versions = list_prompt_versions()
        prompt_id = st.selectbox("Prompt version", versions, index=versions.index(DEFAULT_PROMPT_ID))
        enforce_schema = st.checkbox("Enforce JSON schema in the API", value=False)
        if provider_choice.startswith("Qwen") and prompt_id in ("v2_fewshot", "v4_best"):
            st.info("Few-shot prompts send 2 example photos, so Qwen on Groq accepts only 1 claim photo.")

    left, right = st.columns([1, 1])
    with left:
        uploads = st.file_uploader(
            f"Car photos (1 to {MAX_IMAGES})", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True
        )
        description = st.text_area("What happened?", placeholder="Hit a pole while reversing")
        c1, c2 = st.columns(2)
        make = c1.text_input("Make", "Maruti Suzuki")
        model = c2.text_input("Model", "Swift")
        year = c1.number_input("Year", min_value=1990, max_value=2027, value=2021)
        fuel = c2.selectbox("Fuel", ["petrol", "diesel", "cng", "electric", "hybrid"])
        run = st.button("Assess damage", type="primary", disabled=not uploads)
        if uploads:
            st.image([u.getvalue() for u in uploads], caption=[f"Photo {i}" for i in range(len(uploads))], width=180)

    if not run:
        return
    images = [ImageInput(u.getvalue(), u.type or "image/jpeg") for u in uploads]
    vehicle = {"make": make, "model": model, "year": int(year), "fuel": fuel}
    with right:
        try:
            provider = build_provider(provider_choice)
        except RuntimeError as error:
            st.error(str(error))
            return
        with st.spinner("Looking at the photos..."):
            result = assess_damage(images, vehicle, provider, description, prompt_id, enforce_schema)

        if not result.ok:
            st.error(f"Could not produce a damage report ({result.error.error_code}): {result.error.message}")
            st.json(result.error.model_dump())
            return

        report = result.report
        for flag in report.image_quality_flags:
            st.warning(f"{describe_flag(flag)}. A clearer photo would give a more reliable result.")
        if not report.damages:
            st.success("No visible damage found.")
        else:
            st.subheader(f"{len(report.damages)} damage(s) found")
            st.dataframe(
                [
                    {
                        "Part": d.part.replace("_", " "),
                        "Damage": d.damage_type.replace("_", " "),
                        "Severity": SEVERITY_BADGE[d.severity],
                        "Confidence": f"{d.confidence:.0%}",
                        "Photo": d.image_index,
                        "Notes": d.notes,
                    }
                    for d in report.damages
                ],
                hide_index=True,
                use_container_width=True,
            )
        retry_text = f", {result.retries_used} repair retry" if result.retries_used else ""
        st.caption(
            f"{report.model_used} · {report.prompt_strategy} · {result.latency_s:.1f} s · "
            f"{result.input_tokens} in / {result.output_tokens} out tokens{retry_text}"
        )
        contract_json = report.model_dump_json(indent=2)
        st.download_button("Download Contract A JSON", contract_json, file_name=f"{report.claim_id}.json")
        with st.expander("Contract A JSON", expanded=False):
            st.code(contract_json, language="json")


main()
