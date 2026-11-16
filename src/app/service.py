"""End-to-end claim orchestration using the Role 1, 2, and 3 components."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rank_bm25 import BM25Okapi

from src.cost.cost_engine import calculate_estimate
from src.rag.pipeline import run_role3_pipeline
from src.vision.adapter import run_vision
from src.vision.assess import MAX_IMAGES
from src.vision.schema import CLAIM_ID_PATTERN

MAX_POLICY_PDF_BYTES = 2_500_000
MAX_POLICY_PAGES = 300
MAX_POLICY_TEXT_CHARS = 1_000_000
POLICY_CHUNK_CHARS = 1_400
POLICY_CHUNK_OVERLAP = 200
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_QUERY_EXPANSIONS = {
    "accident": "collision accidental event",
    "damage": "loss destruction physical damage",
    "coverage": "cover indemnify insured vehicle",
    "claim conditions": "claim notification proof loss procedure",
    "deductible": "excess compulsory excess",
    "exclusions": "excluded exclusion not covered limitation",
    "repair": "repairing replacement parts",
}


class ClaimWorkflowError(ValueError):
    """Raised for invalid workflow inputs or unusable policy documents."""


class VisionAssessmentError(RuntimeError):
    """Raised when vision returns a structured error instead of Contract A."""


def _safe_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", basename).strip(" .")
    return safe[:120] or "uploaded-policy.pdf"


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


def _expand_query(query: str) -> str:
    lowered = query.casefold()
    extra_terms = [expansion for phrase, expansion in _QUERY_EXPANSIONS.items() if phrase in lowered]
    return " ".join([query, *extra_terms])


def extract_policy_chunks(pdf_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Extract page-cited text chunks from a user-supplied policy PDF."""
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ClaimWorkflowError("Upload a non-empty policy PDF.")
    if len(pdf_bytes) > MAX_POLICY_PDF_BYTES:
        raise ClaimWorkflowError("The policy PDF is too large; use a PDF under 2.5 MB.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise ClaimWorkflowError("The policy PDF is password-protected.")
        page_count = len(reader.pages)
        if page_count == 0:
            raise ClaimWorkflowError("The policy PDF contains no pages.")
        if page_count > MAX_POLICY_PAGES:
            raise ClaimWorkflowError(f"The policy PDF exceeds the {MAX_POLICY_PAGES}-page limit.")
    except ClaimWorkflowError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise ClaimWorkflowError("The uploaded file is not a readable PDF.") from exc

    source_name = _safe_filename(filename)
    chunks: list[dict[str, Any]] = []
    extracted_chars = 0
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except (PdfReadError, OSError, ValueError) as exc:
            raise ClaimWorkflowError(f"Could not extract text from policy page {page_number}.") from exc
        text = " ".join(text.split())
        if not text:
            continue
        extracted_chars += len(text)
        if extracted_chars > MAX_POLICY_TEXT_CHARS:
            raise ClaimWorkflowError("The policy PDF contains too much extractable text.")

        step = POLICY_CHUNK_CHARS - POLICY_CHUNK_OVERLAP
        for start in range(0, len(text), step):
            chunk_text = text[start : start + POLICY_CHUNK_CHARS].strip()
            if chunk_text:
                chunks.append(
                    {
                        "text": chunk_text,
                        "page": page_number,
                        "file_name": source_name,
                    }
                )

    if not chunks:
        raise ClaimWorkflowError(
            "No selectable text was found in the policy PDF. Scanned PDFs need OCR before upload."
        )
    return chunks


class UploadedPolicyRetriever:
    """Request-scoped BM25 retrieval over one uploaded policy document."""

    def __init__(self, chunks: list[dict[str, Any]], insurer: str, uin: str) -> None:
        self.insurer = insurer
        self.uin = uin
        self.chunks = chunks
        self._documents = [chunk for chunk in chunks if _tokenize(chunk["text"])]
        if not self._documents:
            raise ClaimWorkflowError("The uploaded policy has no searchable text.")
        self._index = BM25Okapi([_tokenize(chunk["text"]) for chunk in self._documents])
        self.initialized = True

    def retrieve(
        self,
        query: str,
        insurer: str,
        uin: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if insurer != self.insurer or uin != self.uin:
            return []
        query_tokens = _tokenize(_expand_query(query))
        if not query_tokens:
            return []
        scores = self._index.get_scores(query_tokens)
        if not any(score > 0 for score in scores):
            query_terms = set(query_tokens)
            scores = [
                float(len(query_terms.intersection(_tokenize(chunk["text"]))))
                for chunk in self._documents
            ]
        ranked = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
        results = []
        for index in ranked:
            score = float(scores[index])
            if score <= 0 or len(results) >= max(1, min(top_k, 10)):
                break
            chunk = self._documents[index]
            results.append(
                {
                    "chunk_id": f"{chunk['file_name']}:{chunk['page']}:{index}",
                    "text": chunk["text"],
                    "metadata": {
                        "insurer": self.insurer,
                        "uin": self.uin,
                        "file_name": chunk["file_name"],
                        "page": chunk["page"],
                    },
                }
            )
        return results


def run_claim(
    photo_bytes_list: list[bytes],
    vehicle: dict[str, Any],
    description: str,
    insurer: str,
    policy_uin: str,
    policy_pdf_bytes: bytes,
    policy_filename: str,
    claim_id: str | None = None,
    *,
    claim_llm_client=None,
    vision_runner=None,
    estimate_calculator=None,
    claim_pipeline=None,
) -> dict[str, Any]:
    """Run vision, estimate repair costs, and draft a policy-grounded claim."""
    if not isinstance(photo_bytes_list, list) or not 1 <= len(photo_bytes_list) <= MAX_IMAGES:
        raise ClaimWorkflowError(f"Upload between 1 and {MAX_IMAGES} vehicle photos.")
    if any(not isinstance(photo, bytes) or not photo for photo in photo_bytes_list):
        raise ClaimWorkflowError("Each vehicle photo must be a non-empty image file.")
    if not isinstance(description, str) or not description.strip():
        raise ClaimWorkflowError("Describe what happened before submitting the claim.")
    if not isinstance(vehicle, dict):
        raise ClaimWorkflowError("Vehicle details are required.")
    if any(not isinstance(vehicle.get(field), str) or not vehicle[field].strip() for field in ("make", "model", "fuel")):
        raise ClaimWorkflowError("Vehicle make, model, and fuel type are required.")
    year = vehicle.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not 1980 <= year <= 2100:
        raise ClaimWorkflowError("Vehicle year must be an integer from 1980 to 2100.")
    if not isinstance(insurer, str) or not insurer.strip():
        raise ClaimWorkflowError("Enter the insurer name shown on the policy.")
    if not isinstance(policy_uin, str) or not policy_uin.strip():
        raise ClaimWorkflowError("Enter the policy UIN shown on the policy.")
    if claim_id and not re.fullmatch(CLAIM_ID_PATTERN, claim_id):
        raise ClaimWorkflowError("Claim ID must use the format CLM-YYYYMMDD-NNN.")

    chunks = extract_policy_chunks(policy_pdf_bytes, policy_filename)
    retriever = UploadedPolicyRetriever(chunks, insurer.strip(), policy_uin.strip())
    vision_call = vision_runner or run_vision
    estimate_call = estimate_calculator or calculate_estimate
    claim_call = claim_pipeline or run_role3_pipeline

    contract_a = vision_call(photo_bytes_list, vehicle, description.strip(), claim_id)
    if not isinstance(contract_a, dict):
        raise VisionAssessmentError("Vision returned an invalid response.")
    if "error_code" in contract_a:
        code = contract_a.get("error_code", "provider_error")
        message = contract_a.get("message", "Vision could not assess the uploaded photos.")
        if code == "bad_input":
            raise ClaimWorkflowError(f"Vision input validation failed: {message}")
        raise VisionAssessmentError(f"{code}: {message}")

    try:
        contract_b = estimate_call(contract_a)
    except (KeyError, ValueError) as exc:
        raise ClaimWorkflowError(f"Cost estimate could not be calculated: {exc}") from exc
    contract_c = claim_call(
        contract_a,
        contract_b,
        insurer.strip(),
        policy_uin.strip(),
        retriever=retriever,
        llm_client=claim_llm_client,
    )
    return {
        "claim_id": contract_a["claim_id"],
        "status": "incomplete_estimate" if contract_b["unpriced_parts"] else "draft_ready",
        "contract_a": contract_a,
        "contract_b": contract_b,
        "contract_c": contract_c,
    }
