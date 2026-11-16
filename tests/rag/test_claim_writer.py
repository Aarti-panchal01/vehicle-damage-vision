import copy
import json
from pathlib import Path

import pytest

from src.rag.claim_writer import (
    ClaimDraftError,
    build_contract_c_estimate_fields,
    check_matching_claim_ids,
    generate_claim_draft,
    load_contract_b_schema,
    retrieve_policy_evidence,
    validate_contract_b,
    validate_contract_c_estimate_fields,
)
from src.rag.pipeline import run_role3_pipeline

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "tests" / "fixtures" / "contract_b"
CONTRACT_A_DIR = ROOT / "mocks"


@pytest.fixture(autouse=True)
def configure_test_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini-flash")


@pytest.fixture(params=sorted(SAMPLE_DIR.glob("*_contract_b.json")), ids=lambda p: p.stem)
def contract_b(request):
    with request.param.open(encoding="utf-8") as sample_file:
        return json.load(sample_file)


@pytest.fixture
def contract_a(contract_b):
    for sample_path in CONTRACT_A_DIR.glob("contract_a_*.json"):
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        if sample.get("claim_id") == contract_b["claim_id"]:
            return sample
    raise AssertionError("No Contract A mock matches {}".format(contract_b["claim_id"]))


def test_actual_role2_sample_validates_against_copied_schema(contract_b):
    DraftSchema = load_contract_b_schema()
    assert DraftSchema["title"] == "Contract B: Cost estimate"
    validate_contract_b(contract_b)


def test_invalid_contract_b_is_rejected(contract_b):
    invalid = copy.deepcopy(contract_b)
    del invalid["currency"]
    with pytest.raises(ValueError, match="Invalid Contract B"):
        validate_contract_b(invalid)


def test_matching_claim_ids_are_accepted(contract_a, contract_b):
    assert check_matching_claim_ids(contract_a, contract_b) == contract_b["claim_id"]


def test_mismatching_claim_ids_are_rejected(contract_a, contract_b):
    contract_a["claim_id"] = "different-claim"
    with pytest.raises(ValueError, match="do not match"):
        build_contract_c_estimate_fields(contract_a, contract_b)


def test_line_items_are_preserved_exactly(contract_a, contract_b):
    mapped = build_contract_c_estimate_fields(contract_a, contract_b)
    assert mapped["line_items"] == contract_b["line_items"]


def test_all_monetary_values_and_totals_are_preserved(contract_a, contract_b):
    mapped = build_contract_c_estimate_fields(contract_a, contract_b)
    monetary_fields = (
        "part_cost", "labour_cost", "paint_cost", "depreciation_pct",
        "depreciation_amount", "claimable_amount",
    )
    for source_item, mapped_item in zip(contract_b["line_items"], mapped["line_items"]):
        assert {key: mapped_item[key] for key in monetary_fields} == {
            key: source_item[key] for key in monetary_fields
        }
    for name in ("gross", "depreciation", "claimable"):
        assert mapped["totals"][name] == contract_b["totals"][name]


def test_currency_age_and_unpriced_parts_are_preserved(contract_a, contract_b):
    mapped = build_contract_c_estimate_fields(contract_a, contract_b)
    assert mapped["totals"]["currency"] == contract_b["currency"]
    assert mapped["totals"]["vehicle_age_years"] == contract_b["vehicle_age_years"]
    assert mapped["totals"]["unpriced_parts"] == contract_b["unpriced_parts"]


def test_inputs_are_not_mutated(contract_a, contract_b):
    original_a, original_b = copy.deepcopy(contract_a), copy.deepcopy(contract_b)
    mapped = build_contract_c_estimate_fields(contract_a, contract_b)
    if mapped["line_items"]:
        mapped["line_items"][0]["part"] = "changed in output only"
    mapped["totals"]["unpriced_parts"].append("changed in output only")
    assert contract_a == original_a
    assert contract_b == original_b


def test_mapped_fields_are_compatible_with_contract_c(contract_a, contract_b):
    mapped = build_contract_c_estimate_fields(contract_a, contract_b)
    validate_contract_c_estimate_fields(mapped)


class MockRetriever:
    initialized = True

    def __init__(self, metadata=None, results=None):
        self.metadata = metadata or {
            "insurer": "TATA AIG", "uin": "POLICY-UIN",
            "file_name": "policy.pdf", "page": 3,
            "policy_section": "Section I", "policy_scope": "own_damage",
        }
        self.results = results
        self.calls = []

    def retrieve(self, query, insurer=None, uin=None, top_k=5):
        self.calls.append((query, insurer, uin, top_k))
        if self.results is not None:
            return self.results
        return [{"metadata": self.metadata, "text": "Section I states accidental vehicle damage wording.",
                 "chunk_id": "test-chunk", "hybrid_score": 0.04}]


class MockGeminiResponse:
    def __init__(self, text):
        self.text = text


class MockGeminiModels:
    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return MockGeminiResponse(self.response or json.dumps({
            "summary": "Draft based on supplied damage and estimate information.",
            "policy_justification": [{
                "statement": "The retrieved wording describes the stated vehicle policy terms.",
                "source": "policy.pdf", "page": 3,
            }],
            "exclusions_flagged": [],
            "disclaimer": "Coverage requires verification.",
        }))


class MockGeminiClient:
    def __init__(self, response=None):
        self.models = MockGeminiModels(response)


def draft_for(contract_a, contract_b, retriever, llm_client=None):
    return run_role3_pipeline(contract_a, contract_b, "TATA AIG", "POLICY-UIN", retriever=retriever,
                              llm_client=llm_client or MockGeminiClient())


def test_complete_contract_c_and_scoped_retrieval(contract_a, contract_b):
    retriever = MockRetriever()
    llm = MockGeminiClient()
    result = draft_for(contract_a, contract_b, retriever, llm)
    assert set(result) == {"claim_id", "summary", "line_items", "totals", "policy_justification", "exclusions_flagged", "disclaimer"}
    assert len(retriever.calls) == 3
    assert all(call[1:3] == ("TATA AIG", "POLICY-UIN") for call in retriever.calls)
    assert result["policy_justification"][0]["source"] == "policy.pdf"
    assert result["policy_justification"][0]["page"] == 3
    assert len(llm.models.calls) == 1
    request = json.loads(llm.models.calls[0]["contents"])
    assert request["contract_a"] == contract_a
    assert "contract_b" not in request
    assert request["selected_insurer"] == "TATA AIG"
    assert request["selected_policy_uin"] == "POLICY-UIN"
    assert len(request["retrieved_policy_chunks"]) <= 5
    assert request["retrieved_policy_chunks"][0]["source_document"] == "policy.pdf"
    assert "application/json" == llm.models.calls[0]["config"]["response_mime_type"]
    assert set(llm.models.calls[0]["config"]["response_schema"]["properties"]) == {
        "summary", "policy_justification", "exclusions_flagged", "disclaimer"
    }
    assert llm.models.calls[0]["config"]["thinking_config"] == {"thinking_level": "low"}
    assert result["line_items"] == contract_b["line_items"]
    for key, value in contract_b["totals"].items():
        assert result["totals"][key] == value


@pytest.mark.parametrize("metadata", [
    {"insurer": "ACKO", "uin": "POLICY-UIN", "file_name": "p.pdf", "page": 1},
    {"insurer": "TATA AIG", "uin": "OTHER-UIN", "file_name": "p.pdf", "page": 1},
])
def test_mismatched_insurer_or_uin_evidence_rejected(contract_a, contract_b, metadata):
    with pytest.raises(ClaimDraftError, match="different insurer or policy UIN"):
        draft_for(contract_a, contract_b, MockRetriever(metadata=metadata))


def test_no_evidence_fails_safely(contract_a, contract_b):
    with pytest.raises(ClaimDraftError, match="No policy evidence"):
        draft_for(contract_a, contract_b, MockRetriever(results=[]))


def test_gemini_malformed_json_is_clear_generation_error(contract_a, contract_b):
    from src.rag.claim_writer import ClaimGenerationError
    with pytest.raises(ClaimGenerationError, match="malformed JSON"):
        draft_for(contract_a, contract_b, MockRetriever(), MockGeminiClient("not-json"))


def test_unsupported_model_citation_is_rejected(contract_a, contract_b):
    from src.rag.claim_writer import ClaimGenerationError
    response = json.dumps({
        "summary": "Summary",
        "policy_justification": [{"statement": "A clause", "source": "other.pdf", "page": 88}],
        "exclusions_flagged": [], "disclaimer": "Review required.",
    })
    with pytest.raises(ClaimGenerationError, match="absent from retrieved"):
        draft_for(contract_a, contract_b, MockRetriever(), MockGeminiClient(response))


def test_missing_gemini_api_key_is_configuration_error(contract_a, contract_b, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini-flash")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ClaimDraftError, match="GEMINI_API_KEY is missing"):
        generate_claim_draft(contract_a, contract_b, "TATA AIG", "POLICY-UIN", retriever=MockRetriever())


def test_gemini_client_uses_single_attempt_timeout_and_closes(monkeypatch, contract_a, contract_b):
    from google import genai
    from google.genai import types

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-gemini-flash")
    monkeypatch.setitem(types.ThinkingConfig.model_fields, "thinking_level", None)
    client = MockGeminiClient()
    client.close_calls = 0

    def close():
        client.close_calls += 1

    client.close = close
    client_kwargs = []

    def client_factory(**kwargs):
        client_kwargs.append(kwargs)
        return client

    monkeypatch.setattr(genai, "Client", client_factory)
    result = generate_claim_draft(
        contract_a, contract_b, "TATA AIG", "POLICY-UIN", retriever=MockRetriever()
    )

    assert result["claim_id"] == contract_a["claim_id"]
    assert len(client_kwargs) == 1
    assert client_kwargs[0]["http_options"].timeout == 120000
    assert client_kwargs[0]["http_options"].retry_options.attempts == 1
    assert len(client.models.calls) == 1
    assert client.close_calls == 1


def test_evidence_ranking_limits_unique_chunks_and_covers_each_query(contract_a, contract_b):
    base_meta = MockRetriever().metadata

    def candidate(chunk_id):
        return {
            "metadata": dict(base_meta),
            "text": f"Policy evidence for {chunk_id}.",
            "chunk_id": chunk_id,
        }

    class QueryRetriever(MockRetriever):
        def retrieve(self, query, insurer=None, uin=None, top_k=5):
            index = len(self.calls)
            self.calls.append((query, insurer, uin, top_k))
            results = [
                [candidate("shared"), candidate("q0-second"), candidate("q0-third")],
                [candidate("shared"), candidate("q1-only"), candidate("q1-third")],
                [candidate("q2-only"), candidate("shared"), candidate("q2-third")],
            ][index]
            return results

    retriever = QueryRetriever()
    evidence = retrieve_policy_evidence(contract_a, contract_b, "TATA AIG", "POLICY-UIN", retriever)
    chunk_ids = [item["text"].removeprefix("Policy evidence for ").removesuffix(".") for item in evidence]
    assert len(evidence) <= 5
    assert len(chunk_ids) == len(set(chunk_ids))
    assert {"shared", "q1-only", "q2-only"}.issubset(set(chunk_ids))
    assert len(retriever.calls) == 3


def test_model_response_only_contributes_narrative_fields(contract_a, contract_b):
    from src.rag.claim_writer import ClaimGenerationError

    malicious_numeric_response = json.dumps({
        "summary": "Narrative only.",
        "policy_justification": [{"statement": "Policy wording.", "source": "policy.pdf", "page": 3}],
        "exclusions_flagged": [],
        "disclaimer": "Review required.",
        "claim_id": "model-id-must-be-ignored",
        "line_items": [],
        "totals": {"gross": -1},
    })
    with pytest.raises(ClaimGenerationError, match="exactly the Contract C fields"):
        draft_for(contract_a, contract_b, MockRetriever(), MockGeminiClient(malicious_numeric_response))


def test_old_sdk_fails_before_model_call_when_thinking_level_is_unsupported(monkeypatch):
    from google.genai import types

    from src.rag.claim_writer import _gemini_client

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delitem(types.ThinkingConfig.model_fields, "thinking_level", raising=False)
    with pytest.raises(ClaimDraftError, match="lacks Gemini 3 thinking_level support"):
        _gemini_client()


@pytest.mark.parametrize("insurer,uin", [(None, "POLICY-UIN"), ("TATA AIG", None), ("", "POLICY-UIN"), ("TATA AIG", "")])
def test_missing_policy_identity_rejected(contract_a, contract_b, insurer, uin):
    with pytest.raises(ClaimDraftError):
        generate_claim_draft(contract_a, contract_b, insurer, uin, retriever=MockRetriever())


def test_summary_uses_only_supplied_claim_facts(contract_a, contract_b):
    summary = draft_for(contract_a, contract_b, MockRetriever())["summary"]
    assert summary == "Draft based on supplied damage and estimate information."
    assert "approved" not in summary.casefold()


def test_exclusions_only_flagged_when_evidence_and_claim_facts_match(contract_a, contract_b):
    evidence = [{"insurer": "TATA AIG", "uin": "POLICY-UIN", "file_name": "policy.pdf", "page": 3,
                 "text": "The Company shall not be liable for theft losses."}]
    # The supplied sample describes a parking collision, not theft.
    result = draft_for(contract_a, contract_b, MockRetriever(results=[{
        "metadata": MockRetriever().metadata, "text": evidence[0]["text"], "chunk_id": "exclusion"
    }]))
    assert result["exclusions_flagged"] == []


def test_estimate_values_and_incomplete_depreciation_disclosures(contract_a, contract_b):
    original_items = copy.deepcopy(contract_b["line_items"])
    original_totals = copy.deepcopy(contract_b["totals"])
    result = draft_for(contract_a, contract_b, MockRetriever())
    assert result["line_items"] == original_items
    for key, value in original_totals.items():
        assert result["totals"][key] == value
    assert result["line_items"] == original_items
    assert "depreciation assumptions originate from a Shriram policy" in result["disclaimer"]
    assert result["totals"]["unpriced_parts"] == contract_b["unpriced_parts"]
    if contract_b["unpriced_parts"]:
        assert "estimate is incomplete" in result["disclaimer"]


def test_inputs_are_unchanged_by_complete_pipeline(contract_a, contract_b):
    original_a, original_b = copy.deepcopy(contract_a), copy.deepcopy(contract_b)
    draft_for(contract_a, contract_b, MockRetriever())
    assert contract_a == original_a
    assert contract_b == original_b
