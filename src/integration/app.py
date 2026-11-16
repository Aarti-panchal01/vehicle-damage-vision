
import json
import re
import html
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ==================================================
# 1. CONFIGURATION
# ==================================================

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

from src.integration.pipeline import process_claim
from src.integration.pdf_report import generate_claim_pdf

st.set_page_config(
    page_title="Vehicle Damage Vision",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================================================
# 2. INSURER INFORMATION
# ==================================================

INSURER_UINS = {
    "ACKO": "IRDAN157RPMT0013V01202526",
    "Go Digit": "IRDAN158RPMT0035V01202425",
    "HDFC ERGO": "IRDAN146RPMT0041V01202425",
    "Liberty General": "IRDAN150RP0035V02201213",
    "New India Assurance": "",
    "SBI General": "IRDAN144RPMT0022V01202425",
    "TATA AIG": "IRDAN108RPMT0002V02200001",
    "Universal Sompo": "IRDAN134RP0004V03200708"
}

# ==================================================
# 3. CUSTOM CSS
# ==================================================

st.markdown("""
<style>

/* Main background */
.stApp {
    background-color: #f4f7fb;
    color: #26364f;
}

[data-testid="stMain"] {
    background-color: #f4f7fb;
}

.block-container {
    max-width: 1450px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

/* Main headings */
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {
    color: #14233d !important;
    font-weight: 700;
}

/* Hero banner */
.hero {
    background: linear-gradient(120deg, #101d36, #2456a6);
    padding: 32px;
    border-radius: 16px;
    margin-bottom: 28px;
    box-shadow: 0 5px 18px rgba(16, 29, 54, 0.12);
}

.hero h1 {
    color: #ffffff !important;
    font-size: 34px;
    margin-bottom: 8px;
}

.hero p {
    color: #e0eaff !important;
    font-size: 15px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #101d36;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
    color: #ffffff !important;
}

/* Form containers */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #ffffff;
    border-radius: 13px;
}

/* Input labels */
.stTextInput label,
.stNumberInput label,
.stTextArea label,
.stSelectbox label,
.stFileUploader label {
    color: #17243b !important;
    font-weight: 600;
}

/* Input fields */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background-color: #ffffff !important;
    color: #17243b !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px;
}

/* Metrics */
[data-testid="stMetric"] {
    background-color: #ffffff;
    padding: 18px;
    border-radius: 12px;
    border: 1px solid #e5eaf1;
}

[data-testid="stMetricLabel"] {
    color: #52627a !important;
}

[data-testid="stMetricValue"] {
    color: #14233d !important;
}

/* Tables */
[data-testid="stDataFrame"] {
    background-color: #ffffff;
    border-radius: 10px;
}

/* Expanders */
[data-testid="stExpander"] {
    background-color: #ffffff;
    border: 1px solid #e5eaf1;
    border-radius: 10px;
}

/* Buttons */
.stButton button,
.stDownloadButton button {
    border-radius: 9px;
    font-weight: 600;
}

/* Captions */
[data-testid="stCaptionContainer"] {
    color: #64748b !important;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# 4. REUSABLE DISPLAY HELPERS
# ==================================================

def show_message(message, kind="success"):
    """Display readable custom status messages."""

    styles = {
        "success": {
            "background": "#e8f7ee",
            "color": "#17643a",
            "border": "#a7dfba",
            "icon": "✓"
        },
        "warning": {
            "background": "#fff5df",
            "color": "#805400",
            "border": "#f0d18c",
            "icon": "⚠"
        },
        "error": {
            "background": "#fdecec",
            "color": "#a32626",
            "border": "#f2b8b8",
            "icon": "✕"
        },
        "info": {
            "background": "#eaf2ff",
            "color": "#173c70",
            "border": "#bfd4f5",
            "icon": "ℹ"
        }
    }

    style = styles.get(kind, styles["info"])
    safe_message = html.escape(str(message))

    st.markdown(
        f"""
        <div style="
            background:{style['background']};
            color:{style['color']};
            border:1px solid {style['border']};
            padding:15px 18px;
            border-radius:10px;
            margin:10px 0;
            line-height:1.6;
        ">
            <strong>{style['icon']} {safe_message}</strong>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_disclaimer(message):
    """Display a readable disclaimer card."""

    safe_message = html.escape(str(message))

    st.markdown(
        f"""
        <div style="
            background:#eaf2ff;
            color:#173c70;
            padding:20px;
            border-radius:10px;
            border:1px solid #bfd4f5;
            line-height:1.8;
            margin-top:10px;
        ">
            <strong>Important Disclaimer</strong>
            <br><br>
            {safe_message}
        </div>
        """,
        unsafe_allow_html=True
    )


# ==================================================
# 5. HEADER
# ==================================================

st.markdown("""
<div class="hero">
    <h1>🚘 Vehicle Damage Vision</h1>
    <p>
        AI-powered vehicle damage detection, repair cost estimation
        and intelligent insurance claim analysis.
    </p>
</div>
""", unsafe_allow_html=True)


# ==================================================
# 6. SIDEBAR
# ==================================================

st.sidebar.title("🚘 Vehicle Damage Vision")
st.sidebar.caption("Insurance Claim Assessment Platform")

page = st.sidebar.radio(
    "Navigation",
    ["New Claim", "About"]
)

st.sidebar.divider()
st.sidebar.caption("AI-Powered Claim Assessment System")


# ==================================================
# 7. ABOUT PAGE
# ==================================================

if page == "About":

    st.title("About Vehicle Damage Vision")

    st.write("""
    Vehicle Damage Vision is an AI-powered vehicle insurance
    claim assessment system designed to simplify vehicle damage
    analysis and insurance claim preparation.
    """)

    st.subheader("System Architecture")

    st.markdown("""
    **Role 1 – Vehicle Damage Detection**

    Identifies damaged vehicle components using AI and computer vision.

    **Role 2 – Repair Cost Estimation**

    Estimates repair, labour, painting and depreciation costs.

    **Role 3 – Insurance Policy Analysis**

    Retrieves relevant policy clauses and generates an
    evidence-grounded claim draft.

    **Role 4 – System Integration**

    Connects all modules through a unified application and
    presents the complete claim assessment.
    """)

    st.divider()

    st.subheader("Technology Stack")

    st.write("""
    Python | Streamlit | Gemini API | Computer Vision |
    ChromaDB | Retrieval-Augmented Generation
    """)

    st.stop()


# ==================================================
# 8. NEW CLAIM PAGE
# ==================================================

st.title("New Insurance Claim")

st.caption(
    "Enter vehicle information, insurance details and damage photographs."
)


# ==================================================
# 9. VEHICLE INFORMATION
# ==================================================

with st.container(border=True):

    st.subheader("1. Vehicle Information")

    col1, col2 = st.columns(2)

    with col1:

        make = st.text_input(
            "Vehicle Make",
            value="Maruti Suzuki"
        )

        model = st.text_input(
            "Vehicle Model",
            value="Swift"
        )

        year = st.number_input(
            "Manufacturing Year",
            min_value=1990,
            max_value=date.today().year,
            value=2021
        )

    with col2:

        fuel = st.selectbox(
            "Fuel Type",
            ["petrol", "diesel", "cng", "electric", "hybrid"]
        )

        claim_id = st.text_input(
            "Claim ID",
            value=f"CLM-{date.today():%Y%m%d}-001"
        )

        insurer = st.selectbox(
            "Insurance Company",
            list(INSURER_UINS.keys()),
            key="selected_insurer"
        )


# ==================================================
# 10. INSURANCE POLICY
# ==================================================

with st.container(border=True):

    st.subheader("2. Insurance Policy")

    # Use a separate key for each insurer so that
    # changing the insurer selects its corresponding default.

    policy_key = f"policy_uin_{insurer}"

    if policy_key not in st.session_state:
        st.session_state[policy_key] = INSURER_UINS[insurer]

    policy_uin = st.text_input(
        "Insurance Policy UIN",
        key=policy_key,
        help="Verify this UIN against the actual policy document."
    )


# ==================================================
# 11. DAMAGE INFORMATION
# ==================================================

with st.container(border=True):

    st.subheader("3. Damage Information")

    description = st.text_area(
        "Describe the vehicle damage",
        placeholder=(
            "Describe where and how the vehicle was damaged..."
        ),
        height=120
    )

    uploaded_images = st.file_uploader(
        "Upload Vehicle Damage Photographs",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True
    )

    if uploaded_images:

        st.write("Uploaded Photographs")

        columns = st.columns(min(len(uploaded_images), 3))

        for index, uploaded_image in enumerate(uploaded_images):

            with columns[index % len(columns)]:

                st.image(
                    uploaded_image,
                    caption=uploaded_image.name,
                    use_container_width=True
                )


# ==================================================
# 12. PROCESS CLAIM
# ==================================================

st.divider()

submitted = st.button(
    "🔍 Analyse Vehicle & Process Claim",
    type="primary",
    use_container_width=True
)


if submitted:

    errors = []

    if not make.strip():
        errors.append("Enter vehicle make.")

    if not model.strip():
        errors.append("Enter vehicle model.")

    if not uploaded_images:
        errors.append("Upload at least one vehicle photograph.")

    if not description.strip():
        errors.append("Enter the accident description.")

    if not claim_id.strip():
        errors.append("Enter a claim ID.")

    elif not re.fullmatch(
        r"CLM-\d{8}-\d{3}",
        claim_id.strip()
    ):
        errors.append(
            "Claim ID must follow CLM-YYYYMMDD-XXX format."
        )

    if not insurer.strip():
        errors.append("Select an insurance company.")

    if not policy_uin.strip():
        errors.append("Enter the exact insurance policy UIN.")

    if errors:

        for error in errors:
            show_message(error, "error")

    else:

        st.session_state.pop("claim_result", None)
        st.session_state.pop("claim_images", None)

        with st.spinner(
            "Processing claim through Roles 1, 2, 3 and 4..."
        ):

            try:

                photos = [
                    image.getvalue()
                    for image in uploaded_images
                ]

                result = process_claim(
                    photo_bytes_list=photos,
                    vehicle={
                        "make": make.strip(),
                        "model": model.strip(),
                        "year": int(year),
                        "fuel": fuel
                    },
                    description=description.strip(),
                    insurer=insurer,
                    policy_uin=policy_uin.strip(),
                    claim_id=claim_id.strip()
                )
                if isinstance(result, dict):
                    result["insurer"] = insurer
                    result["policy_uin"] = policy_uin.strip()

                st.session_state["claim_result"] = result
                st.session_state["claim_images"] = photos
            except Exception as error:

                show_message(
                    f"Claim processing failed: {error}",
                    "error"
                )

                st.exception(error)


# ==================================================
# 13. CLAIM ANALYSIS RESULTS
# ==================================================

result = st.session_state.get("claim_result")


if result:

    st.divider()

    st.header("📊 Claim Analysis Results")

    if not result.get("success"):

        show_message(
            "Processing stopped at: {}".format(
                result.get("stage", "Unknown stage")
            ),
            "error"
        )

        error_details = result.get("error", {})

        if isinstance(error_details, (dict, list)):
            st.json(error_details)
        else:
            st.error(str(error_details))
        if result.get("contract_a"):
            with st.expander("View Contract A"):
                st.json(result["contract_a"])

        if result.get("contract_b"):
            with st.expander("View Contract B"):
                st.json(result["contract_b"])

    else:

        contract_a = result["contract_a"]
        contract_b = result["contract_b"]
        contract_c = result["contract_c"]

        totals = contract_b.get("totals", {})

        show_message(
            "All four roles completed successfully!",
            "success"
        )

        # ------------------------------------------
        # CLAIM OVERVIEW
        # ------------------------------------------

        st.subheader("Claim Overview")

        c1, c2, c3 = st.columns(3)

        vehicle = contract_a.get("vehicle", {})

        c1.metric(
            "Claim ID",
            result.get("claim_id", "N/A")
        )

        c2.metric(
            "Vehicle",
            "{} {}".format(
                vehicle.get("make", ""),
                vehicle.get("model", "")
            )
        )

        c3.metric(
            "Detected Damage",
            len(contract_a.get("damages", []))
        )

        st.divider()

        # ------------------------------------------
        # ROLE 1 – DAMAGE DETECTION
        # ------------------------------------------

        st.subheader("🔍 Role 1 – Damage Detection")

        left, right = st.columns(2)

        with left:

            images = st.session_state.get("claim_images", [])

            if images:

                st.image(
                    images[0],
                    caption="Uploaded Vehicle Photograph",
                    use_container_width=True
                )

        with right:

            st.markdown("**Detected Damage Details**")

            damages = contract_a.get("damages", [])

            if damages:

                for damage in damages:

                    confidence = damage.get("confidence")

                    confidence_text = (
                        f"{confidence:.0%}"
                        if isinstance(confidence, (int, float))
                        else "N/A"
                    )

                    st.markdown(
                        f"""
                        **Part:** {damage.get('part', 'N/A')}

                        **Damage Type:** {damage.get('damage_type', 'N/A')}

                        **Severity:** {damage.get('severity', 'N/A')}

                        **Confidence:** {confidence_text}

                        **Notes:** {damage.get('notes', 'N/A')}
                        """
                    )

                    st.divider()

            else:

                st.info("No visible damage detected.")

        if contract_a.get("image_quality_flags"):

            show_message(
                "Image quality warnings: " +
                ", ".join(
                    map(str, contract_a["image_quality_flags"])
                ),
                "warning"
            )

        with st.expander("View Complete Contract A"):
            st.json(contract_a)

        st.divider()

        # ------------------------------------------
        # ROLE 2 – COST ESTIMATION
        # ------------------------------------------

        st.subheader("💰 Role 2 – Repair Cost Estimation")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Gross Estimate",
            "₹{:,.2f}".format(
                totals.get("gross", 0)
            )
        )

        c2.metric(
            "Depreciation",
            "₹{:,.2f}".format(
                totals.get("depreciation", 0)
            )
        )

        c3.metric(
            "Claimable Estimate",
            "₹{:,.2f}".format(
                totals.get("claimable", 0)
            )
        )

        st.caption(
            "Estimated values only. These are not insurer-approved amounts."
        )

        st.markdown("**Repair Cost Breakdown**")

        line_items = contract_b.get("line_items", [])

        if line_items:

            st.dataframe(
                line_items,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info("No repair line items available.")

        unpriced_parts = (
            contract_b.get("unpriced_parts")
            or totals.get("unpriced_parts", [])
        )

                # Flag missing or zero prices only when a part is being replaced.
        zero_price_parts = [
            item.get("part", "Unknown part")
            for item in line_items
            if item.get("action") == "replace"
            and (
                item.get("part_cost") is None
                or item.get("part_cost") == 0
            )
        ]

        if unpriced_parts:

            show_message(
                "Some parts have no verified price: " +
                ", ".join(map(str, unpriced_parts)),
                "warning"
            )

        if zero_price_parts:

            show_message(
                "Zero or missing part price detected for: " +
                ", ".join(zero_price_parts) +
                ". Verify the price with the Role 2 owner.",
                "warning"
            )

        with st.expander("View Complete Contract B"):
            st.json(contract_b)

        st.divider()

        # ------------------------------------------
        # ROLE 3 – POLICY ANALYSIS
        # ------------------------------------------

        st.subheader(
            "📄 Role 3 – Policy Evidence & Claim Draft"
        )

        st.markdown("**AI-Generated Claim Summary**")

        st.write(
            contract_c.get(
                "summary",
                "No summary available."
            )
        )

        st.markdown("**Policy Justifications**")

        justifications = contract_c.get(
            "policy_justification", []
        )

        if justifications:

            for index, item in enumerate(justifications, 1):

                with st.container(border=True):

                    st.markdown(
                        f"**Policy Evidence {index}**"
                    )

                    st.write(
                        item.get("statement", "")
                    )

                    st.caption(
                        "Source: {} | Page: {}".format(
                            item.get("source", "N/A"),
                            item.get("page", "N/A")
                        )
                    )

        else:

            show_message(
                "No policy justifications were generated.",
                "warning"
            )

        # Potential exclusions
        st.markdown("**Potential Exclusions**")

        exclusions = contract_c.get(
            "exclusions_flagged", []
        )

        if exclusions:

            for exclusion in exclusions:
                show_message(exclusion, "warning")

        else:

            show_message(
                "No potential exclusions were flagged.",
                "success"
            )

        # Disclaimer
        disclaimer = contract_c.get(
            "disclaimer",
            "Final claim determination requires insurer verification."
        )

        show_disclaimer(disclaimer)

        with st.expander("View Complete Contract C"):
            st.json(contract_c)

        st.divider()

        # ------------------------------------------
        # DOWNLOAD REPORT
        # ------------------------------------------

        st.subheader("📥 Download Claim Report")

        # Generate reports only when a complete successful claim exists.
        if result and result.get("success"):
            report_json = json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                default=str
            )

            pdf_report = generate_claim_pdf(result)

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    label="📄 Download PDF Report",
                    data=pdf_report,
                    file_name=f"{result.get('claim_id', 'claim')}_report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            with col2:
                st.download_button(
                    label="📥 Download JSON Report",
                    data=report_json,
                    file_name=f"{result.get('claim_id', 'claim')}_report.json",
                    mime="application/json",
                    use_container_width=True
                )

            st.caption(
                "Download the integrated assessment containing outputs from Roles 1, 2 and 3."
            )
        else:
            st.info("Process a successful claim to download its reports.")


# ==================================================
# 14. FOOTER
# ==================================================

st.divider()

st.caption(
    "Vehicle Damage Vision | AI-Powered Insurance Claim Assessment"
)
