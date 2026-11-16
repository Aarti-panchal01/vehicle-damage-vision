"""Deterministic Contract B adapter and evidence-grounded Contract C drafts."""

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft202012Validator
from src.rag.retriever import HybridPolicyRetriever


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_B_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "contract_b.schema.json"
CONTRACT_C_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "contract_c.schema.json"
CONTRACT_A_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "contract_a.schema.json"


class ClaimDraftError(ValueError):
    """Raised when inputs or policy evidence cannot support a safe draft."""


CLAIM_SYSTEM_PROMPT = """You write an AI-generated insurance claim draft from supplied facts and policy evidence.
Use only the supplied policy chunks for policy statements. Cite the exact source document and page for every policy justification.
Never invent coverage, exclusions, clauses, sources, or page numbers. Explain relevant wording in relation to supplied damage facts without asserting that the claim is covered.
Flag drunk-driving, invalid-licence, mechanical-breakdown, wear-and-tear, or other exclusions only when the supplied evidence supports the exclusion and the supplied claim facts make it relevant. Describe a relevant exclusion as potential and subject to review, never as a confirmed denial.
Do not claim insurer approval or guaranteed coverage or settlement. Return only the narrative fields summary, policy_justification, exclusions_flagged, and disclaimer as JSON. Do not generate claim identifiers, estimates, or monetary values; the application restores estimate fields from Contract B."""

EVIDENCE_CHUNK_LIMIT = 5
RRF_K = 60
NARRATIVE_FIELDS = ("summary", "policy_justification", "exclusions_flagged", "disclaimer")
NARRATIVE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "policy_justification": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "statement": {"type": "STRING"},
                    "source": {"type": "STRING"},
                    "page": {"type": "STRING"},
                },
                "required": ["statement", "source", "page"],
            },
        },
        "exclusions_flagged": {"type": "ARRAY", "items": {"type": "STRING"}},
        "disclaimer": {"type": "STRING"},
    },
    "required": list(NARRATIVE_FIELDS),
}


class ClaimGenerationError(ClaimDraftError):
    """Raised when Gemini cannot produce valid, evidence-cited narrative fields."""


def _load_schema(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft202012Validator.check_schema(schema)
    return schema


def load_contract_b_schema() -> Dict[str, Any]:
    """Load and check the copied Role 2 Contract B schema."""
    return _load_schema(CONTRACT_B_SCHEMA_PATH)


def validate_contract_b(contract_b: Dict[str, Any]) -> None:
    """Raise ValueError with field paths when data violates Contract B."""
    validator = Draft202012Validator(load_contract_b_schema())
    errors = sorted(validator.iter_errors(contract_b), key=lambda e: list(map(str, e.path)))
    if errors:
        messages = []
        for error in errors:
            path = ".".join(str(part) for part in error.absolute_path) or "contract_b"
            messages.append("{}: {}".format(path, error.message))
        raise ValueError("Invalid Contract B: " + "; ".join(messages))


def check_matching_claim_ids(contract_a: Dict[str, Any], contract_b: Dict[str, Any]) -> str:
    """Return the shared claim ID, rejecting missing or mismatched IDs."""
    claim_a = contract_a.get("claim_id")
    claim_b = contract_b.get("claim_id")
    if not claim_a or not claim_b:
        raise ValueError("Contract A and Contract B must both provide claim_id.")
    if claim_a != claim_b:
        raise ValueError("Contract A and Contract B claim_id values do not match.")
    return claim_a


def build_contract_c_estimate_fields(
    contract_a: Dict[str, Any], contract_b: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the Contract C estimate fields, preserving Contract B values.

    Contract B is schema-validated first. Deep copies prevent callers from
    sharing mutable line-item, totals, or unpriced-parts objects with output.
    Monetary values are copied without calculation or normalization.
    """
    validate_contract_b(contract_b)
    claim_id = check_matching_claim_ids(contract_a, contract_b)
    totals = copy.deepcopy(contract_b["totals"])
    totals.update({
        "currency": contract_b["currency"],
        "vehicle_age_years": contract_b["vehicle_age_years"],
        "unpriced_parts": copy.deepcopy(contract_b["unpriced_parts"]),
    })
    fields = {
        "claim_id": claim_id,
        "line_items": copy.deepcopy(contract_b["line_items"]),
        "totals": totals,
    }
    validate_contract_c_estimate_fields(fields)
    return fields


def validate_contract_c_estimate_fields(fields: Dict[str, Any]) -> None:
    """Check mapped fields against the corresponding Contract C properties."""
    schema = _load_schema(CONTRACT_C_SCHEMA_PATH)
    properties = schema["properties"]
    unexpected = set(fields) - set(properties)
    if unexpected:
        raise ValueError("Unexpected Contract C fields: {}".format(sorted(unexpected)))
    errors = []
    for name, value in fields.items():
        validator = Draft202012Validator(properties[name])
        for error in validator.iter_errors(value):
            errors.append("{}: {}".format(name, error.message))
    if errors:
        raise ValueError("Contract C estimate fields are incompatible: " + "; ".join(errors))


def validate_contract_a(contract_a: Dict[str, Any]) -> None:
    """Validate a Contract A report against the shared schema."""
    validator = Draft202012Validator(_load_schema(CONTRACT_A_SCHEMA_PATH))
    errors = list(validator.iter_errors(contract_a))
    if errors:
        raise ValueError("Invalid Contract A: " + "; ".join(e.message for e in errors))


def validate_contract_c(contract_c: Dict[str, Any]) -> None:
    """Validate the complete generated object against Contract C."""
    validator = Draft202012Validator(_load_schema(CONTRACT_C_SCHEMA_PATH))
    errors = list(validator.iter_errors(contract_c))
    if errors:
        raise ValueError("Invalid Contract C: " + "; ".join(e.message for e in errors))


def build_retrieval_queries(contract_a: Dict[str, Any], contract_b: Dict[str, Any]):
    """Build deterministic policy queries from claim facts and estimate context."""
    accident = contract_a.get("user_description", "")
    damages = [
        "{} {} {}".format(d.get("part", ""), d.get("damage_type", ""), d.get("notes", ""))
        for d in contract_a.get("damages", [])
    ]
    repairs = ["{} {}".format(i["part"], i["action"]) for i in contract_b["line_items"]]
    facts = " ".join([accident] + damages + repairs).strip()
    if not facts:
        facts = "motor policy claim"
    return [
        "Policy coverage relevant to this vehicle accident and damage: " + facts,
        "Policy exclusions and limitations potentially relevant to this accident: " + facts,
        "Claim notification, claim conditions and deductibles relevant to: " + facts,
    ]


def retrieve_policy_evidence(contract_a, contract_b, insurer, uin, retriever=None, top_k=5):
    """Fuse the three scoped query rankings into at most five unique chunks."""
    if not isinstance(insurer, str) or not insurer.strip():
        raise ClaimDraftError("Selected insurer is required.")
    if not isinstance(uin, str) or not uin.strip():
        raise ClaimDraftError("Selected policy UIN is required.")
    retriever = retriever or HybridPolicyRetriever()
    if not retriever.initialized:
        retriever.initialize()
    candidates = {}
    per_query = []
    for query_index, query in enumerate(build_retrieval_queries(contract_a, contract_b)):
        results = retriever.retrieve(query, insurer=insurer, uin=uin, top_k=top_k)
        query_rankings = []
        query_seen = set()
        for rank, result in enumerate(results, start=1):
            metadata = result.get("metadata") or {}
            if metadata.get("insurer") != insurer or metadata.get("uin") != uin:
                raise ClaimDraftError("Retriever returned evidence for a different insurer or policy UIN.")
            if not metadata.get("file_name") or metadata.get("page") is None or not result.get("text", "").strip():
                continue
            chunk_id = result.get("chunk_id")
            if chunk_id is None:
                stable_payload = "\0".join((
                    str(metadata["file_name"]), str(metadata["page"]), result["text"]
                ))
                chunk_id = hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
            key = str(chunk_id)
            if key in query_seen:
                continue
            query_seen.add(key)
            query_rankings.append(key)
            if key not in candidates:
                candidates[key] = {
                    "item": {
                        "insurer": metadata["insurer"],
                        "uin": metadata["uin"],
                        "source_document": metadata["file_name"],
                        "page": metadata["page"],
                        "policy_section": metadata.get("policy_section"),
                        "policy_scope": metadata.get("policy_scope"),
                        "text": result["text"],
                    },
                    "score": 0.0,
                    "query_indexes": set(),
                    "order": len(candidates),
                }
            candidates[key]["score"] += 1.0 / (RRF_K + rank)
            candidates[key]["query_indexes"].add(query_index)
        per_query.append(query_rankings)
    if not candidates:
        raise ClaimDraftError("No policy evidence matched the selected insurer and UIN.")

    ranked_ids = sorted(candidates, key=lambda key: (-candidates[key]["score"], candidates[key]["order"]))
    selected = ranked_ids[:EVIDENCE_CHUNK_LIMIT]
    # Keep a representative from each query intent when evidence exists. If a
    # query is missing from the RRF top five, replace the lowest-ranked item
    # that is not the sole representative of another intent.
    for query_index, query_ranking in enumerate(per_query):
        if not query_ranking or any(query_index in candidates[key]["query_indexes"] for key in selected):
            continue
        replacement = next((key for key in query_ranking if key not in selected), None)
        if replacement is None:
            continue
        removable = [
            key for key in selected
            if all(
                any(other != key and other in selected and intent in candidates[other]["query_indexes"]
                    for other in selected)
                for intent in candidates[key]["query_indexes"]
            )
        ]
        if removable:
            lowest = min(removable, key=lambda key: (candidates[key]["score"], -candidates[key]["order"]))
            selected[selected.index(lowest)] = replacement

    selected.sort(key=lambda key: (-candidates[key]["score"], candidates[key]["order"]))
    evidence = []
    for key in selected:
        item = candidates[key]["item"]
        item["retrieval_score"] = candidates[key]["score"]
        evidence.append(item)
    return evidence


def _claim_summary(contract_a, contract_b):
    vehicle = contract_a["vehicle"]
    vehicle_text = "{} {} {} ({})".format(vehicle["year"], vehicle["make"], vehicle["model"], vehicle["fuel"])
    damage_text = "; ".join(
        "{}: {} {}".format(d["part"], d["severity"], d["damage_type"])
        for d in contract_a["damages"]
    ) or "Contract A reports no visible damage"
    repairs = "; ".join("{} ({})".format(i["part"], i["action"]) for i in contract_b["line_items"])
    repair_text = repairs or "no priced repair line items"
    return (
        "AI-generated draft for claim {}. Contract A's user-described circumstances are: '{}'. "
        "Contract A describes {} and records: {}. Contract B supplies {}. Its claimable estimate total is {} {} "
        "and is not an approval or payment commitment. Policy wording is summarized separately in cited evidence."
    ).format(contract_a["claim_id"], contract_a.get("user_description", ""), vehicle_text, damage_text, repair_text,
             contract_b["currency"], contract_b["totals"]["claimable"])


def _evidence_statement(text):
    excerpt = " ".join(text.split())
    if len(excerpt) > 900:
        excerpt = excerpt[:897].rsplit(" ", 1)[0] + "..."
    return "The retrieved policy wording states: " + excerpt


def _relevant_exclusion_flags(contract_a, evidence):
    """Flag only explicit exclusions whose subject is named in claim facts."""
    facts = " ".join([
        contract_a.get("user_description", ""),
        " ".join("{} {} {}".format(d.get("part", ""), d.get("damage_type", ""), d.get("notes", ""))
                 for d in contract_a.get("damages", [])),
    ]).casefold()
    flags = []
    for item in evidence:
        text = " ".join(item["text"].casefold().split())
        exclusion = any(term in text for term in ("not be liable", "not covered", "excluded", "exclusion"))
        subject_terms = ("theft", "flood", "fire", "alcohol", "intoxicating liquor", "wear and tear", "mechanical breakdown")
        matched = [term for term in subject_terms if term in text and term in facts]
        if exclusion and matched:
            flags.append("Potential exclusion concerning {} appears in the retrieved wording; applicability requires insurer or human review.".format(", ".join(matched)))
    return list(dict.fromkeys(flags))


def _gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ClaimDraftError("Gemini is not configured: GEMINI_API_KEY is missing.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ClaimDraftError("Gemini client dependency is missing; install google-genai.") from exc
    if "thinking_level" not in getattr(types.ThinkingConfig, "model_fields", {}):
        raise ClaimDraftError(
            "Installed google-genai lacks Gemini 3 thinking_level support; upgrade the runtime to Python 3.10+ and google-genai>=2.0.0."
        )
    http_options = types.HttpOptions(
        timeout=120000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    return genai.Client(api_key=api_key, http_options=http_options)


def _generate_narrative(client, model_name, contract_a, contract_b, insurer, uin, evidence):
    request = {
        "contract_a": contract_a,
        "selected_insurer": insurer,
        "selected_policy_uin": uin,
        "retrieved_policy_chunks": evidence,
    }
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=json.dumps(request, ensure_ascii=False),
            config={
                "system_instruction": CLAIM_SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_schema": NARRATIVE_RESPONSE_SCHEMA,
                "thinking_config": {"thinking_level": "low"},
                "max_output_tokens": 1200,
            },
        )
    except Exception as exc:
        # Preserve the real Gemini SDK/API error so the UI can show its cause.
        raise ClaimGenerationError(
            "Gemini API request failed ({}): {}".format(type(exc).__name__, exc)
        ) from exc

    # Gemini can return no text when a response is blocked, truncated, or otherwise
    # has no candidate text. Check that explicitly before attempting JSON parsing.
    try:
        response_text = response.text
    except Exception as exc:
        raise ClaimGenerationError(
            "Could not read Gemini response text ({}): {}".format(type(exc).__name__, exc)
        ) from exc

    if not isinstance(response_text, str) or not response_text.strip():
        prompt_feedback = getattr(response, "prompt_feedback", None)
        candidates = getattr(response, "candidates", None)
        raise ClaimGenerationError(
            "Gemini returned an empty response. "
            "Prompt feedback: {!r}. Candidates: {!r}".format(
                prompt_feedback, candidates
            )
        )

    try:
        output = json.loads(response_text)
    except json.JSONDecodeError as exc:
        # Include only a short preview; never expose credentials or request payloads.
        preview = response_text[:300].replace("\\n", " ")
        raise ClaimGenerationError(
            "Gemini returned malformed JSON ({} at position {}). Response preview: {!r}".format(
                exc.msg, exc.pos, preview
            )
        ) from exc
    except (AttributeError, TypeError) as exc:
        raise ClaimGenerationError(
            "Gemini response could not be parsed ({}): {}".format(type(exc).__name__, exc)
        ) from exc
    if not isinstance(output, dict):
        raise ClaimGenerationError("Gemini response must be one Contract C JSON object.")
    allowed = set(NARRATIVE_FIELDS)
    if set(output) != allowed:
        raise ClaimGenerationError("Gemini response must contain exactly the Contract C fields.")
    for key in ("summary", "policy_justification", "exclusions_flagged", "disclaimer"):
        if key not in output:
            raise ClaimGenerationError("Gemini response is missing narrative field {}.".format(key))
    if not isinstance(output["summary"], str) or not output["summary"].strip():
        raise ClaimGenerationError("Gemini response has an empty or invalid summary.")
    if not isinstance(output["disclaimer"], str) or not output["disclaimer"].strip():
        raise ClaimGenerationError("Gemini response has an empty or invalid disclaimer.")
    if not isinstance(output["exclusions_flagged"], list) or any(not isinstance(x, str) for x in output["exclusions_flagged"]):
        raise ClaimGenerationError("Gemini response has invalid exclusions_flagged.")
    if not isinstance(output["policy_justification"], list) or not output["policy_justification"]:
        raise ClaimGenerationError("Gemini response must include policy justifications.")
    allowed_citations = {(item["source_document"], str(item["page"])) for item in evidence}
    for item in output["policy_justification"]:
        if not isinstance(item, dict) or set(item) != {"statement", "source", "page"}:
            raise ClaimGenerationError("Gemini returned a malformed policy justification.")
        if not isinstance(item["statement"], str) or not item["statement"].strip():
            raise ClaimGenerationError("Gemini returned an empty policy statement.")
        if (item["source"], str(item["page"])) not in allowed_citations:
            raise ClaimGenerationError("Gemini cited a source or page absent from retrieved policy evidence.")
    return output


def generate_claim_draft(contract_a, contract_b, insurer, uin, retriever=None, top_k=5, llm_client=None):
    """Generate one Gemini narrative and restore all estimate values deterministically."""
    validate_contract_a(contract_a)
    validate_contract_b(contract_b)
    check_matching_claim_ids(contract_a, contract_b)
    model_name = os.getenv("GEMINI_MODEL")
    if not model_name:
        raise ClaimDraftError("Gemini is not configured: GEMINI_MODEL is missing.")
    owns_llm_client = llm_client is None
    if owns_llm_client:
        llm_client = _gemini_client()
    try:
        evidence = retrieve_policy_evidence(contract_a, contract_b, insurer, uin, retriever, top_k)
        narrative = _generate_narrative(llm_client, model_name, contract_a, contract_b, insurer, uin, evidence)
        estimate = build_contract_c_estimate_fields(contract_a, contract_b)
        required_disclaimer = (
            "This is an AI-generated draft, not an insurer coverage decision. Coverage and settlement require insurer verification. "
            "Role 2 depreciation assumptions originate from a Shriram policy and must be checked against the selected policy. "
            "Retrieved clauses are evidence only and do not guarantee coverage or settlement."
        )
        if contract_b["unpriced_parts"]:
            required_disclaimer += " The estimate is incomplete because some parts are unpriced; the claimable total is not an approved or guaranteed payable amount."
        draft = {
            "claim_id": estimate["claim_id"],
            "summary": narrative["summary"],
            "line_items": estimate["line_items"],
            "totals": estimate["totals"],
            "policy_justification": narrative["policy_justification"],
            "exclusions_flagged": narrative["exclusions_flagged"],
            "disclaimer": narrative["disclaimer"] + " " + required_disclaimer,
        }
        try:
            validate_contract_c(draft)
        except ValueError as exc:
            raise ClaimGenerationError("Gemini claim draft is invalid against Contract C: {}".format(exc)) from exc
        return draft
    finally:
        if owns_llm_client:
            close = getattr(llm_client, "close", None)
            if callable(close):
                close()
