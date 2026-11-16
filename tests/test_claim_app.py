import copy
import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import app as vercel_app
from src.app import service
from src.rag.claim_writer import validate_contract_c

ROOT_DIR = Path(__file__).resolve().parents[1]


class FakeModels:
    def generate_content(self, model, contents, config):
        request = json.loads(contents)
        evidence = request["retrieved_policy_chunks"][0]
        response = {
            "summary": "Draft summary for human review.",
            "policy_justification": [
                {
                    "statement": "The cited wording should be reviewed against the complete policy.",
                    "source": evidence["source_document"],
                    "page": str(evidence["page"]),
                }
            ],
            "exclusions_flagged": [],
            "disclaimer": "This output is only a draft.",
        }
        return SimpleNamespace(text=json.dumps(response))


class FakeGeminiClient:
    models = FakeModels()


def _sample_contract_a():
    path = ROOT_DIR / "mocks" / "contract_a_001_dev_01.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _policy_chunks():
    return [
        {
            "text": (
                "The insurer covers accidental loss or damage to the insured vehicle, "
                "subject to the policy terms, conditions, exclusions, and claim notification requirements."
            ),
            "page": 7,
            "file_name": "sample-policy.pdf",
        },
        {
            "text": "Personal accident cover has separate limits and conditions.",
            "page": 22,
            "file_name": "sample-policy.pdf",
        },
    ]


def _text_policy_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(
        b"BT /F1 12 Tf 72 720 Td "
        b"(Accidental damage coverage for insured vehicle) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _jpeg_bytes():
    output = BytesIO()
    Image.new("RGB", (4, 4), color="red").save(output, format="JPEG")
    return output.getvalue()


def test_run_claim_completes_vision_cost_and_policy_draft(monkeypatch):
    monkeypatch.setattr(service, "extract_policy_chunks", lambda pdf, name: _policy_chunks())
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    contract_a = _sample_contract_a()

    def vision_runner(photo_bytes_list, vehicle, description, claim_id):
        assert photo_bytes_list == [b"photo-bytes"]
        assert vehicle == contract_a["vehicle"]
        assert description == contract_a["user_description"]
        assert claim_id == contract_a["claim_id"]
        return copy.deepcopy(contract_a)

    result = service.run_claim(
        photo_bytes_list=[b"photo-bytes"],
        vehicle=contract_a["vehicle"],
        description=contract_a["user_description"],
        insurer="Test Insurer",
        policy_uin="TEST-UIN-001",
        policy_pdf_bytes=b"%PDF test",
        policy_filename="sample-policy.pdf",
        claim_id=contract_a["claim_id"],
        claim_llm_client=FakeGeminiClient(),
        vision_runner=vision_runner,
    )

    assert result["claim_id"] == contract_a["claim_id"]
    assert result["contract_b"]["claim_id"] == result["contract_c"]["claim_id"]
    assert result["contract_c"]["line_items"] == result["contract_b"]["line_items"]
    assert result["contract_c"]["totals"] == result["contract_b"]["totals"] | {
        "currency": result["contract_b"]["currency"],
        "vehicle_age_years": result["contract_b"]["vehicle_age_years"],
        "unpriced_parts": result["contract_b"]["unpriced_parts"],
    }
    assert result["contract_c"]["policy_justification"][0]["source"] == "sample-policy.pdf"
    assert result["contract_c"]["policy_justification"][0]["page"] == "7"
    validate_contract_c(result["contract_c"])
    expected_status = "incomplete_estimate" if result["contract_b"]["unpriced_parts"] else "draft_ready"
    assert result["status"] == expected_status


def test_run_claim_stops_when_vision_returns_error(monkeypatch):
    monkeypatch.setattr(service, "extract_policy_chunks", lambda pdf, name: _policy_chunks())

    def unexpected_call(*args, **kwargs):
        pytest.fail("The estimate and claim stages must not run after a vision error.")

    with pytest.raises(service.VisionAssessmentError, match="quota_exhausted"):
        service.run_claim(
            photo_bytes_list=[b"photo-bytes"],
            vehicle={"make": "Make", "model": "Model", "year": 2021, "fuel": "petrol"},
            description="A parking collision",
            insurer="Test Insurer",
            policy_uin="TEST-UIN-001",
            policy_pdf_bytes=b"%PDF test",
            policy_filename="sample-policy.pdf",
            vision_runner=lambda *args: {
                "error_code": "quota_exhausted",
                "message": "Provider quota is unavailable.",
            },
            estimate_calculator=unexpected_call,
            claim_pipeline=unexpected_call,
        )


def test_policy_pdf_parser_rejects_invalid_input():
    with pytest.raises(service.ClaimWorkflowError, match="readable PDF"):
        service.extract_policy_chunks(b"not a PDF", "policy.pdf")


def test_policy_pdf_parser_extracts_text_with_page_and_filename():
    chunks = service.extract_policy_chunks(_text_policy_pdf(), "folder/policy.pdf")

    assert len(chunks) == 1
    assert chunks[0]["text"] == "Accidental damage coverage for insured vehicle"
    assert chunks[0]["page"] == 1
    assert chunks[0]["file_name"] == "policy.pdf"


def test_vercel_app_serves_ui_and_static_assets():
    client = TestClient(vercel_app.app)

    home = client.get("/")
    stylesheet = client.get("/static/styles.css")

    assert home.status_code == 200
    assert "Prepare a claim draft" in home.text
    assert "Before you begin" not in home.text
    assert "App access password" not in home.text
    assert stylesheet.status_code == 200
    assert "--green-dark" in stylesheet.text


def test_vercel_runtime_import_does_not_require_local_static_directory():
    environment = os.environ.copy()
    environment["VERCEL"] = "1"
    code = "import app; print(any(getattr(route, 'path', None) == '/static' for route in app.app.routes))"

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        env=environment,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_health_does_not_require_an_app_password_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("APP_ACCESS_PASSWORD", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "configured-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")

    response = TestClient(vercel_app.app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "gemini_configured": True,
        "model_configured": True,
    }


def test_vercel_claim_endpoint_passes_valid_uploads_to_workflow(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("APP_ACCESS_PASSWORD", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "configured-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    captured = {}
    expected = {"claim_id": "CLM-20260910-001", "status": "draft_ready"}

    def fake_run_claim(**kwargs):
        captured.update(kwargs)
        return expected

    monkeypatch.setattr(vercel_app, "run_claim", fake_run_claim)
    client = TestClient(vercel_app.app)
    photo_bytes = _jpeg_bytes()
    response = client.post(
        "/api/claims",
        data={
            "vehicle_make": "Maruti Suzuki",
            "vehicle_model": "Swift",
            "vehicle_year": "2021",
            "vehicle_fuel": "petrol",
            "description": "A parking collision",
            "insurer": "Test Insurer",
            "policy_uin": "TEST-UIN-001",
            "claim_id": "CLM-20260910-001",
            "confirm_external_processing": "true",
        },
        files=[
            ("photos", ("photo.jpg", photo_bytes, "image/jpeg")),
            ("policy_pdf", ("policy.pdf", _text_policy_pdf(), "application/pdf")),
        ],
    )

    assert response.status_code == 200
    assert response.json() == expected
    assert captured["photo_bytes_list"] == [photo_bytes]
    assert captured["vehicle"] == {
        "make": "Maruti Suzuki",
        "model": "Swift",
        "year": 2021,
        "fuel": "petrol",
    }
    assert captured["policy_pdf_bytes"].startswith(b"%PDF")
    assert captured["insurer"] == "Test Insurer"
    assert captured["policy_uin"] == "TEST-UIN-001"
