"""Public Role 3 pipeline for validated claim-draft generation."""

from src.rag.claim_writer import generate_claim_draft


def run_role3_pipeline(contract_a, contract_b, insurer, policy_uin, retriever=None, top_k=5, llm_client=None):
    """Validate inputs, retrieve evidence for the exact policy, and return Contract C.

    ``retriever`` is injectable for tests; production calls use the existing
    ``HybridPolicyRetriever`` through the claim-writer evidence function.
    """
    return generate_claim_draft(
        contract_a=contract_a,
        contract_b=contract_b,
        insurer=insurer,
        uin=policy_uin,
        retriever=retriever,
        top_k=top_k,
        llm_client=llm_client,
    )
