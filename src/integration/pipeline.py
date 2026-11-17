from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

from src.vision.adapter import run_vision
from src.cost.cost_engine import calculate_estimate
from src.rag.pipeline import run_role3_pipeline


def process_claim(
    photo_bytes_list,
    vehicle,
    description,
    insurer,
    policy_uin,
    claim_id=None,
    reference_year=None,
    retriever=None,
    llm_client=None,
):
    # ROLE 1: Damage detection
    contract_a = run_vision(
        photo_bytes_list=photo_bytes_list,
        vehicle=vehicle,
        description=description,
        claim_id=claim_id,
    )

    if "error_code" in contract_a:
        return {"success": False, "stage": "vision", "error": contract_a}

    # ROLE 2: Repair cost estimation
    try:
        contract_b = calculate_estimate(
            contract_a,
            reference_year=reference_year,
        )
    except Exception as e:
        return {
            "success": False,
            "stage": "cost",
            "claim_id": contract_a.get("claim_id"),
            "error": str(e),
        }

    # ROLE 3: Policy retrieval and claim drafting
    try:
        contract_c = run_role3_pipeline(
            contract_a=contract_a,
            contract_b=contract_b,
            insurer=insurer,
            policy_uin=policy_uin,
            retriever=retriever,
            llm_client=llm_client,
        )
    except Exception as e:
        return {
            "success": False,
            "stage": "policy_and_claim_draft",
            "claim_id": contract_a.get("claim_id"),
            "contract_a": contract_a,
            "contract_b": contract_b,
            "error": str(e),
        }

    return {
        "success": True,
        "claim_id": contract_a.get("claim_id"),
        "contract_a": contract_a,
        "contract_b": contract_b,
        "contract_c": contract_c,
    }
