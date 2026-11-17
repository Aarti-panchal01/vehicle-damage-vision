
import json
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def generate_claim_pdf(result):
    """Generate a PDF report from a successfully processed claim."""

    if not isinstance(result, dict):
        raise TypeError("Claim result must be a dictionary.")

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Vehicle Damage Vision Claim Report",
        author="Vehicle Damage Vision",
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="VDVTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=25,
        textColor=colors.HexColor("#17365D"),
        alignment=1,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="VDVHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#17365D"),
        spaceBefore=10,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="VDVSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=11,
        spaceAfter=4,
    ))

    story = []

    # ------------------------------------------
    # HELPER FUNCTIONS
    # ------------------------------------------

    def safe(value):
        if value is None:
            return "Not available"

        if isinstance(value, (dict, list)):
            value = json.dumps(
                value,
                ensure_ascii=False,
                default=str
            )

        return escape(str(value)).replace("\n", "<br/>")

    def heading(text):
        story.append(
            Paragraph(
                escape(str(text)),
                styles["VDVHeading"]
            )
        )

    def paragraph(text, small=False):
        style = (
            styles["VDVSmall"]
            if small
            else styles["BodyText"]
        )

        story.append(Paragraph(safe(text), style))
        story.append(Spacer(1, 4))

    def key_value_table(rows):
        table = Table(
            rows,
            colWidths=[48 * mm, 117 * mm],
            repeatRows=1
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#17365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1),
             0.4, colors.HexColor("#D5DDE5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#F3F6FA")
            ]),
        ]))

        story.append(table)
        story.append(Spacer(1, 8))

    def json_section(title, data):
        heading(title)

        if data is None or data == {} or data == []:
            paragraph("No information available.")
            return

        rendered = escape(json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            default=str
        )).replace("\n", "<br/>")

        story.append(
            Paragraph(rendered, styles["VDVSmall"])
        )

        story.append(Spacer(1, 6))

    # ------------------------------------------
    # EXTRACT CLAIM DATA
    # ------------------------------------------

    contract_a = result.get("contract_a") or {}
    contract_b = result.get("contract_b") or {}
    contract_c = result.get("contract_c") or {}

    if not isinstance(contract_a, dict):
        contract_a = {}

    if not isinstance(contract_b, dict):
        contract_b = {}

    if not isinstance(contract_c, dict):
        contract_c = {}

    vehicle = contract_a.get("vehicle") or {}

    if not isinstance(vehicle, dict):
        vehicle = {}

    totals = contract_b.get("totals") or {}

    if not isinstance(totals, dict):
        totals = {}

    # ------------------------------------------
    # REPORT HEADER
    # ------------------------------------------

    story.append(
        Paragraph(
            "VEHICLE DAMAGE VISION",
            styles["VDVTitle"]
        )
    )

    story.append(
        Paragraph(
            "AI-Powered Insurance Claim Assessment Report",
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 14))

    # ------------------------------------------
    # 1. CLAIM OVERVIEW
    # ------------------------------------------

    heading("1. Claim Overview")

    vehicle_name = " ".join(
        str(vehicle.get(key, "")).strip()
        for key in ("make", "model")
        if vehicle.get(key)
    ) or "See detailed assessment"

    if vehicle.get("year"):
        vehicle_name += f" ({vehicle['year']})"

    if vehicle.get("fuel"):
        vehicle_name += f", {vehicle['fuel']}"

    key_value_table([
        ["Field", "Details"],
        ["Claim ID", safe(result.get("claim_id"))],
        [
            "Claim Status",
            "Successfully processed"
            if result.get("success")
            else "Not successful"
        ],
        ["Vehicle", safe(vehicle_name)],
        [
            "Insurer",
            safe(contract_c.get("insurer") or result.get("insurer"))
        ],
    ])

    # ------------------------------------------
    # ACCIDENT DESCRIPTION
    # ------------------------------------------

    description = (
        contract_a.get("user_description")
        or contract_a.get("accident_description")
        or contract_a.get("description")
        or result.get("description")
    )

    if description:
        heading("Accident Description")
        paragraph(description)

    # ------------------------------------------
    # 2. ROLE 1 - DAMAGE DETECTION
    # ------------------------------------------

    json_section(
        "2. Role 1 - Vehicle Damage Detection",
        contract_a
    )

    # ------------------------------------------
    # 3. ROLE 2 - COST ESTIMATION
    # ------------------------------------------

    json_section(
        "3. Role 2 - Repair Cost Estimation",
        contract_b
    )

    # Identify missing or zero part prices.

    zero_price_parts = []

    for item in contract_b.get("line_items") or []:

        if not isinstance(item, dict):
            continue

        price = item.get("part_cost")

        if price is None or price == 0:
            zero_price_parts.append(
                item.get("part", "Unknown part")
            )

    unpriced_parts = (
        contract_b.get("unpriced_parts")
        or totals.get("unpriced_parts")
        or []
    )

    flagged_parts = sorted({
        str(part)
        for part in list(unpriced_parts) + zero_price_parts
    })

    if flagged_parts:

        heading("Cost Verification Required")

        paragraph(
            "The following parts have missing or zero verified "
            "prices: "
            + ", ".join(flagged_parts)
            + ". Obtain a verified quotation before finalising "
            "the estimate."
        )

    # ------------------------------------------
    # 4. ROLE 3 - POLICY ANALYSIS
    # ------------------------------------------

    json_section(
        "4. Role 3 - Policy Analysis and Claim Draft",
        contract_c
    )

    justifications = (
        contract_c.get("policy_justification") or []
    )

    if justifications:

        heading("Policy Evidence")

        for index, item in enumerate(justifications, start=1):

            if isinstance(item, dict):

                paragraph(
                    f"Evidence {index}: "
                    f"{item.get('statement', 'No statement supplied.')} "
                    f"(Source: {item.get('source', 'Not specified')}; "
                    f"Page: {item.get('page', 'Not specified')})",
                    small=True
                )

            else:
                paragraph(item, small=True)

    exclusions = (
        contract_c.get("exclusions_flagged") or []
    )

    if exclusions:

        heading("Potential Exclusions")

        for exclusion in exclusions:
            paragraph(f"- {exclusion}")

    # ------------------------------------------
    # 5. VALIDATION NOTES
    # ------------------------------------------

    heading("5. Important Validation Notes")

    paragraph(
        "AI-generated damage assessments, repair estimates and "
        "policy interpretations must be reviewed by an authorised "
        "insurance professional before a claim decision is made."
    )

    paragraph(
        "Repair prices, depreciation, policy coverage, exclusions "
        "and claim eligibility should be verified against the "
        "applicable insurer policy and supporting documents."
    )

    # Preserve the Role 3 disclaimer.

    disclaimer = contract_c.get("disclaimer")

    if disclaimer:

        heading("Role 3 Disclaimer")
        paragraph(disclaimer)

    # ------------------------------------------
    # PLATFORM DISCLAIMER
    # ------------------------------------------

    heading("Platform Disclaimer")

    paragraph(
        "This report is generated by the Vehicle Damage Vision "
        "platform for assessment assistance. It is not an official "
        "insurance approval, settlement offer or guarantee of "
        "claim acceptance."
    )

    # ------------------------------------------
    # FOOTER
    # ------------------------------------------

    def footer(canvas, document):

        canvas.saveState()

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)

        canvas.drawString(
            18 * mm,
            10 * mm,
            "Vehicle Damage Vision | AI-Powered Claim Assessment"
        )

        canvas.drawRightString(
            A4[0] - 18 * mm,
            10 * mm,
            f"Page {document.page}"
        )

        canvas.restoreState()

    # ------------------------------------------
    # GENERATE PDF
    # ------------------------------------------

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
