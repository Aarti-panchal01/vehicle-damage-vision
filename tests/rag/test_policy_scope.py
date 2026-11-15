import pytest

from src.rag.chunker import (
    classify_policy_scope,
    clause_aware_chunks,
    extract_sections,
    fixed_size_chunks,
    is_heading,
    pack_sections,
)
from src.rag.retriever import query_policy_scope


@pytest.mark.parametrize(
    "text, expected_scope",
    [
        ("IMT15 Personal Accident Cover", "personal_accident"),
        ("IMT16 Personal Accident to Passengers", "personal_accident"),
        ("IMT19 Cover for Imported Vehicles", "own_damage"),
        ("IMT20 Reduction in the Limit of Liability for Property Damage", "third_party"),
        ("IMT22 Compulsory Deductible", "own_damage"),
        ("IMT24 Electrical Electronic Fittings", "add_on"),
        ("IMT25 CNG/LPG Kit in Bi-Fuel System", "add_on"),
        ("IMT28 Legal Liability to Paid Driver", "third_party"),
    ],
)
def test_endorsement_scope_classification(text, expected_scope):
    scope, _ = classify_policy_scope(text)
    assert scope == expected_scope


def test_general_exceptions_reset_personal_accident_scope():
    scope, title = classify_policy_scope(
        "GENERAL EXCEPTIONS: The Company shall not be liable.",
        "personal_accident",
        "Personal Accident",
    )
    assert scope == "general"
    assert title == "General Exceptions"


@pytest.mark.parametrize("chunker", [fixed_size_chunks, clause_aware_chunks])
def test_chunkers_preserve_source_metadata_and_policy_section(chunker):
    document = _document(
        "Section I - Loss of or Damage to the Vehicle Insured\n"
        "The Company will indemnify the insured against accidental loss or damage.",
    )
    document["metadata"].update({
        "uin": "TEST-UIN",
        "publisher": "Test Publisher",
        "document_category": "insurer_policy_wording",
    })

    chunks = chunker([document])

    assert chunks
    metadata = chunks[0]["metadata"]
    assert metadata["file_name"] == "regression_policy.pdf"
    assert metadata["page"] == 1
    assert metadata["insurer"] == "Test Insurer"
    assert metadata["uin"] == "TEST-UIN"
    assert metadata["publisher"] == "Test Publisher"
    assert metadata["document_category"] == "insurer_policy_wording"
    assert metadata["policy_scope"] == "own_damage"
    assert metadata["policy_section"] == "Section I - Loss of or Damage to the Vehicle Insured"


@pytest.mark.parametrize("chunker", [fixed_size_chunks, clause_aware_chunks])
def test_regulatory_chunks_keep_insurer_identity_blank(chunker):
    document = {
        "text": "Motor Vehicles Rules\n1. Short title and commencement.\n"
        "These rules are made under the Motor Vehicles Act.",
        "metadata": {
            "file_name": "motor_rules.pdf",
            "insurer": "",
            "uin": "",
            "page": 1,
            "publisher": "Government of India",
            "document_category": "regulation",
        },
    }

    chunks = chunker([document])

    assert chunks
    assert all(chunk["metadata"]["insurer"] == "" for chunk in chunks)
    assert all(chunk["metadata"]["uin"] == "" for chunk in chunks)
    assert all(chunk["metadata"]["document_category"] == "regulation" for chunk in chunks)
    assert all(chunk["metadata"]["publisher"] == "Government of India" for chunk in chunks)
    assert all(chunk["metadata"]["policy_scope"] == "regulatory" for chunk in chunks)


def test_general_exceptions_are_separate_packed_chunk():
    sections = [
        {
            "heading": "PERSONAL ACCIDENT COVER",
            "text": "The insurer pays compensation for bodily injury.",
        },
        {
            "heading": "GENERAL EXCEPTIONS",
            "text": "The Company shall not be liable for specified claims.",
        },
        {
            "heading": "1. Driver clause",
            "text": "The vehicle must be driven by an authorised driver.",
        },
    ]

    chunks = pack_sections(sections)

    assert len(chunks) >= 3
    assert "GENERAL EXCEPTIONS" not in chunks[0]
    assert chunks[1].startswith("GENERAL EXCEPTIONS")
    assert "Driver clause" in chunks[2]


def _document(text, page=1):
    return {
        "text": text,
        "metadata": {
            "file_name": "regression_policy.pdf",
            "insurer": "Test Insurer",
            "page": page,
        },
    }


def test_no_claim_bonus_in_unrelated_body_text_does_not_relabel_section():
    chunks = clause_aware_chunks([
        _document(
            "Claim Notification\n"
            "The transfer of the vehicle does not transfer No Claim Bonus. "
            "Notify the insurer as soon as reasonably possible."
        )
    ])

    assert chunks
    assert chunks[0]["metadata"]["policy_section"] == "Claims Procedure"
    assert chunks[0]["metadata"]["policy_section"] != "No Claim Bonus"


def test_genuine_numbered_no_claim_bonus_heading_is_extracted_and_classified():
    text = (
        "9. No Claim Bonus: No Claim Bonus will be allowed at renewal "
        "when no claim was made during the policy year."
    )
    sections = extract_sections(text)
    chunks = clause_aware_chunks([_document(text)])

    assert sections[0]["heading"] == "9. No Claim Bonus"
    assert "will be allowed at renewal" in sections[0]["text"]
    assert chunks[0]["metadata"]["policy_section"] == "No Claim Bonus"
    assert chunks[0]["metadata"]["headings"] == ["9. No Claim Bonus"]


def test_descriptive_no_claim_bonus_heading_is_recognized():
    text = (
        "No Claim Bonus during Policy tenure:\n"
        "An insured becomes entitled to the benefit at renewal."
    )
    sections = extract_sections(text)
    chunks = clause_aware_chunks([_document(text)])

    assert sections[0]["heading"] == "No Claim Bonus during Policy tenure"
    assert chunks[0]["metadata"]["policy_section"] == "No Claim Bonus"


def test_unrelated_section_after_no_claim_bonus_does_not_inherit_its_title():
    chunks = clause_aware_chunks([
        _document(
            "No Claim Bonus\n"
            "A No Claim Bonus is available after a claim-free year.\n\n"
            "Claim Notification\n"
            "The policyholder must notify the insurer promptly."
        )
    ])

    assert len(chunks) == 2
    assert chunks[0]["metadata"]["policy_section"] == "No Claim Bonus"
    assert chunks[1]["metadata"]["policy_section"] == "Claims Procedure"
    assert chunks[1]["metadata"]["policy_scope"] == "general"


def test_general_exceptions_reset_inherited_personal_accident_scope():
    chunks = clause_aware_chunks([
        _document(
            "Section III - Personal Accident Cover\n"
            "The insurer will pay compensation for bodily injury.\n\n"
            "GENERAL EXCEPTIONS\n"
            "The Company shall not be liable for specified events.\n\n"
            "Claim Notification\n"
            "The policyholder must report a claim to the insurer."
        )
    ])

    exception_chunk = next(
        chunk for chunk in chunks
        if chunk["metadata"]["policy_section"] == "General Exceptions"
    )
    notification_chunk = next(
        chunk for chunk in chunks
        if "Claim Notification" in chunk["text"]
    )

    assert exception_chunk["metadata"]["policy_scope"] == "general"
    assert notification_chunk["metadata"]["policy_scope"] == "general"
    assert notification_chunk["metadata"]["policy_section"] == "Claims Procedure"


def test_heading_at_page_end_updates_scope_for_the_next_page():
    chunks = clause_aware_chunks([
        _document(
            "Section III - Personal Accident Cover\n"
            "The insurer will pay compensation for bodily injury.\n\n"
            "GENERAL EXCEPTIONS\n"
            "The Company shall not be liable for specified events.\n\n"
            "CONDITIONS",
            page=1,
        ),
        _document(
            "The policyholder must give written notice immediately after loss.",
            page=2,
        ),
    ])

    next_page_chunk = next(
        chunk for chunk in chunks if chunk["metadata"]["page"] == 2
    )
    assert next_page_chunk["metadata"]["policy_scope"] == "general"
    assert next_page_chunk["metadata"]["policy_section"] == "General Policy Conditions"


def test_body_mention_of_imt_does_not_trigger_endorsement_scope():
    scope, title = classify_policy_scope(
        "General Policy Text\nThis clause refers to IMT15 as an example."
    )

    assert scope == "general"
    assert title == "General Policy Text"


def test_dotted_imt_heading_is_detected():
    heading = "IMT.22. Compulsory Deductible"

    assert is_heading(heading)
    assert classify_policy_scope(heading)[0] == "own_damage"


def test_empty_add_on_headings_set_scope_without_emitting_empty_chunks():
    chunks = clause_aware_chunks([
        _document(
            "Auto Secure – Private Car Package Policy Add-On Covers:\n"
            "TA01 - Depreciation Reimbursement:\n"
            "(UIN: TEST-A001)\n"
            "We will reimburse depreciation deducted on parts replaced."
        )
    ])

    assert len(chunks) == 1
    assert chunks[0]["metadata"]["policy_scope"] == "add_on"
    assert chunks[0]["metadata"]["policy_section"] == "Policy Add-on"


@pytest.mark.parametrize(
    "query, expected_scope",
    [
        (
            "Vehicle damage while driving under the influence of alcohol",
            "own_damage",
        ),
        ("Personal accident compensation for owner driver", "personal_accident"),
        ("What does engine protect flood cover?", "add_on"),
        ("Liability to third parties", "third_party"),
    ],
)
def test_query_scope_classification(query, expected_scope):
    assert query_policy_scope(query) == expected_scope
