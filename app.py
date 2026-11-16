"""Vercel FastAPI entry point for the vehicle claim workflow."""

from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from src.app.service import (
    ClaimWorkflowError,
    MAX_IMAGES,
    VisionAssessmentError,
    run_claim,
)
from src.rag.claim_writer import ClaimDraftError, ClaimGenerationError

ROOT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT_DIR / "public"
MAX_REQUEST_BYTES = 4_000_000
MAX_PHOTO_BYTES = 2_000_000
MAX_IMAGE_PIXELS = 25_000_000
logger = logging.getLogger(__name__)

load_dotenv(ROOT_DIR / ".env")

app = FastAPI(
    title="Vehicle Claim Draft Assistant",
    description="Vision assessment, repair estimate, and policy-grounded claim draft.",
)
if not os.getenv("VERCEL"):
    app.mount("/static", StaticFiles(directory=str(PUBLIC_DIR / "static")), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, bool]:
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    model_configured = bool(os.getenv("GEMINI_MODEL"))
    return {
        "ready": gemini_configured and model_configured,
        "gemini_configured": gemini_configured,
        "model_configured": model_configured,
    }


def _validate_photo(photo_bytes: bytes) -> None:
    try:
        with Image.open(BytesIO(photo_bytes)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(422, "Use a JPEG, PNG, or WebP vehicle photo.")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(422, "A photo exceeds the 25-megapixel limit.")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise HTTPException(422, "One of the uploaded photos is not a valid image.") from exc


@app.post("/api/claims")
def create_claim(
    request: Request,
    photos: list[UploadFile] = File(...),
    policy_pdf: UploadFile = File(...),
    vehicle_make: str = Form(...),
    vehicle_model: str = Form(...),
    vehicle_year: int = Form(...),
    vehicle_fuel: str = Form(...),
    description: str = Form(...),
    insurer: str = Form(...),
    policy_uin: str = Form(...),
    claim_id: str = Form(""),
    confirm_external_processing: bool = Form(False),
) -> dict:
    if not confirm_external_processing:
        raise HTTPException(
            400,
            "Confirm that claim details and selected policy excerpts may be sent to Gemini.",
        )
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("GEMINI_MODEL"):
        raise HTTPException(
            503,
            "Claim drafting is temporarily unavailable. Please try again later.",
        )

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
        raise HTTPException(413, "The total upload exceeds the 4 MB Vercel request limit.")
    if not 1 <= len(photos) <= MAX_IMAGES:
        raise HTTPException(422, f"Upload between 1 and {MAX_IMAGES} vehicle photos.")
    if not (policy_pdf.filename or "").lower().endswith(".pdf"):
        raise HTTPException(422, "Upload the matching policy as a PDF file.")
    if len(description) > 2_000:
        raise HTTPException(422, "The incident description must be 2,000 characters or fewer.")
    if len(insurer) > 120 or len(policy_uin) > 100:
        raise HTTPException(422, "The insurer name or policy UIN is too long.")

    photo_bytes_list = []
    total_bytes = 0
    for photo in photos:
        content = photo.file.read(MAX_PHOTO_BYTES + 1)
        if not content:
            raise HTTPException(422, "An uploaded vehicle photo is empty.")
        if len(content) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Each compressed vehicle photo must be 2 MB or smaller.")
        _validate_photo(content)
        total_bytes += len(content)
        photo_bytes_list.append(content)

    policy_bytes = policy_pdf.file.read(2_500_001)
    if len(policy_bytes) > 2_500_000:
        raise HTTPException(413, "The policy PDF must be 2.5 MB or smaller.")
    total_bytes += len(policy_bytes)
    if total_bytes > MAX_REQUEST_BYTES - 64_000:
        raise HTTPException(413, "The total upload is too large; compress photos or the policy PDF.")

    vehicle = {
        "make": vehicle_make.strip(),
        "model": vehicle_model.strip(),
        "year": vehicle_year,
        "fuel": vehicle_fuel.strip().lower(),
    }
    try:
        return run_claim(
            photo_bytes_list=photo_bytes_list,
            vehicle=vehicle,
            description=description,
            insurer=insurer,
            policy_uin=policy_uin,
            policy_pdf_bytes=policy_bytes,
            policy_filename=policy_pdf.filename or "uploaded-policy.pdf",
            claim_id=claim_id.strip() or None,
        )
    except ClaimWorkflowError as exc:
        raise HTTPException(422, str(exc)) from exc
    except VisionAssessmentError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ClaimGenerationError as exc:
        logger.warning("Claim narrative generation failed: %s", type(exc).__name__)
        raise HTTPException(
            502,
            "Policy claim drafting failed. Check Gemini availability and retry.",
        ) from exc
    except ClaimDraftError as exc:
        status_code = 503 if "not configured" in str(exc).casefold() else 422
        raise HTTPException(status_code, str(exc)) from exc
