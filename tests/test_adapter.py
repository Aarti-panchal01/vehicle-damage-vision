import json

import src.vision.assess as assessment
from src.vision import adapter
from src.vision.prompts import build_request_parts as build_prompt_parts
from src.vision.providers import MockProvider

VEHICLE = {"make": "Honda", "model": "City", "year": 2019, "fuel": "petrol"}
GOOD_REPLY = json.dumps(
    {
        "damages": [],
        "image_quality_flags": [],
    }
)


def test_run_vision_returns_contract_a_using_mock_provider(monkeypatch, tmp_path):
    provider = MockProvider([GOOD_REPLY])
    monkeypatch.setattr(adapter, "make_provider", lambda _name: provider)
    for example_id in ("dev_03", "dev_10"):
        (tmp_path / f"{example_id}.jpg").write_bytes(b"test-image")

    def build_parts(template, images, description, prompt_dir):
        return build_prompt_parts(
            template,
            images,
            description,
            prompt_dir=prompt_dir,
            example_image_dir=tmp_path,
        )

    monkeypatch.setattr(assessment, "build_request_parts", build_parts)

    result = adapter.run_vision([b"fake-image"], VEHICLE, "No visible damage", "CLM-20261115-001")

    assert result["claim_id"] == "CLM-20261115-001"
    assert result["damages"] == []
    assert result["model_used"] == "mock-vlm"
    assert provider.requests


def test_run_vision_returns_bad_input_error_for_invalid_vehicle(monkeypatch):
    provider = MockProvider([GOOD_REPLY])
    monkeypatch.setattr(adapter, "make_provider", lambda _name: provider)

    result = adapter.run_vision([b"fake-image"], {**VEHICLE, "year": 1800}, "", "claim-1")

    assert result["error_code"] == "bad_input"
    assert result["claim_id"] == "claim-1"
    assert not provider.requests


def test_run_vision_returns_bad_input_error_for_invalid_photos():
    result = adapter.run_vision([], VEHICLE, "", "CLM-20261115-003")

    assert result["error_code"] == "bad_input"
    assert result["attempts"] == 0


def test_run_vision_returns_vision_error_when_provider_setup_fails(monkeypatch):
    def fail(_name):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(adapter, "make_provider", fail)

    result = adapter.run_vision([b"fake-image"], VEHICLE, "", "CLM-20261115-002")

    assert result["error_code"] == "provider_error"
    assert result["message"] == "Vision assessment failed (RuntimeError)."
