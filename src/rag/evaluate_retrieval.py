"""Evaluate the existing hybrid policy retriever against a verified gold set."""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.rag.retriever import HybridPolicyRetriever


ROOT_DIR = Path(__file__).resolve().parents[2]
GOLD_SET_PATH = ROOT_DIR / "data" / "evaluation" / "retrieval_gold_set.jsonl"
RESULTS_PATH = ROOT_DIR / "data" / "evaluation" / "retrieval_results.json"
SCOPED_RESULTS_PATH = ROOT_DIR / "data" / "evaluation" / "retrieval_results_scoped.json"
TOP_K = 5
REQUIRED_METADATA = (
    "insurer", "uin", "file_name", "page", "policy_section", "policy_scope"
)


def load_gold_set(path: Path = GOLD_SET_PATH) -> List[Dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not record.get("question_id") or not record.get("expected_sources"):
                raise ValueError("Invalid gold record on line {}".format(line_number))
            records.append(record)

    ids = [record["question_id"] for record in records]
    if len(records) != 30 or len(ids) != len(set(ids)):
        raise ValueError("Gold set must contain exactly 30 uniquely identified questions")
    return records


def result_key(result: Dict[str, Any]) -> Tuple[Any, ...]:
    metadata = result.get("metadata") or {}
    return (
        metadata.get("insurer"), metadata.get("uin"),
        metadata.get("page"), metadata.get("policy_section"),
    )


def is_relevant(result: Dict[str, Any], record: Dict[str, Any]) -> bool:
    key = result_key(result)
    return any(
        key == (
            source.get("insurer", record["insurer"]),
            source.get("policy_uin", record["policy_uin"]),
            source.get("page_number"),
            source.get("policy_section"),
        )
        for source in record["expected_sources"]
    )


def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = len(records)
    if not count:
        return {"question_count": 0, "hit_at_1": 0.0, "hit_at_3": 0.0,
                "hit_at_5": 0.0, "mrr_at_5": 0.0}
    return {
        "question_count": count,
        "hit_at_1": round(sum(1 in r["relevant_ranks"] for r in records) / count, 4),
        "hit_at_3": round(sum(bool([n for n in r["relevant_ranks"] if n <= 3]) for r in records) / count, 4),
        "hit_at_5": round(sum(bool(r["relevant_ranks"]) for r in records) / count, 4),
        "mrr_at_5": round(sum((1.0 / min(r["relevant_ranks"])) if r["relevant_ranks"] else 0.0 for r in records) / count, 4),
    }


def evaluate(insurer_scoped: bool = False) -> Dict[str, Any]:
    gold = load_gold_set()
    retriever = HybridPolicyRetriever()
    retriever.initialize()

    evaluated = []
    wrong_insurer_hits = []
    missing_metadata = []

    for record in gold:
        filters = {"insurer": record["insurer"]} if insurer_scoped else {}
        results = retriever.retrieve(record["question"], top_k=TOP_K, **filters)
        relevant_ranks = [
            rank for rank, result in enumerate(results, start=1)
            if is_relevant(result, record)
        ]
        returned = []
        for rank, result in enumerate(results, start=1):
            metadata = result.get("metadata") or {}
            missing = [key for key in REQUIRED_METADATA if metadata.get(key) is None]
            compact = {
                "rank": rank,
                "chunk_id": result.get("chunk_id"),
                "metadata": metadata,
                "hybrid_score": result.get("hybrid_score"),
                "text_excerpt": result.get("text", "")[:350],
                "relevant": is_relevant(result, record),
                "missing_metadata": missing,
            }
            returned.append(compact)
            if missing:
                missing_metadata.append({
                    "question_id": record["question_id"],
                    "rank": rank,
                    "chunk_id": result.get("chunk_id"),
                    "missing_fields": missing,
                })
            if metadata.get("insurer") and metadata["insurer"] != record["insurer"]:
                wrong_insurer_hits.append({
                    "question_id": record["question_id"],
                    "rank": rank,
                    "expected_insurer": record["insurer"],
                    "returned_insurer": metadata["insurer"],
                    "chunk_id": result.get("chunk_id"),
                })

        evaluated.append({
            "question_id": record["question_id"],
            "question": record["question"],
            "insurer": record["insurer"],
            "expected_sources": record["expected_sources"],
            "relevant_ranks": relevant_ranks,
            "hit_at_1": 1 in relevant_ranks,
            "hit_at_3": any(rank <= 3 for rank in relevant_ranks),
            "hit_at_5": bool(relevant_ranks),
            "reciprocal_rank_at_5": round(1.0 / min(relevant_ranks), 4) if relevant_ranks else 0.0,
            "returned_results": returned,
        })

    by_insurer = {}
    for insurer in sorted({record["insurer"] for record in evaluated}):
        by_insurer[insurer] = summarize(
            [record for record in evaluated if record["insurer"] == insurer]
        )

    results_path = SCOPED_RESULTS_PATH if insurer_scoped else RESULTS_PATH
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gold_set": str(GOLD_SET_PATH.relative_to(ROOT_DIR)),
        "retrieval": {
            "top_k": TOP_K,
            "insurer_filter": "gold-set insurer for each question" if insurer_scoped else None,
            "evaluation_mode": "insurer-scoped; not equivalent to unrestricted cross-insurer search" if insurer_scoped else "unrestricted cross-insurer baseline",
            "relevance": "Exact insurer, policy UIN, page number, and policy section match to any verified expected source.",
            "mrr_definition": "Mean reciprocal rank of the first relevant result within the returned top five (MRR@5).",
        },
        "overall_metrics": summarize(evaluated),
        "per_insurer_metrics": by_insurer,
        "questions": evaluated,
        "failed_hit_at_5": [
            {"question_id": r["question_id"], "question": r["question"], "insurer": r["insurer"]}
            for r in evaluated if not r["hit_at_5"]
        ],
        "incorrect_insurer_retrievals": wrong_insurer_hits,
        "incorrect_insurer_retrieval_count": len(wrong_insurer_hits),
        "missing_metadata_results": missing_metadata,
        "missing_metadata_result_count": len(missing_metadata),
        "metadata_field_missing_counts": dict(Counter(
            field for item in missing_metadata for field in item["missing_fields"]
        )),
    }
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insurer-scoped", action="store_true")
    report = evaluate(insurer_scoped=parser.parse_args().insurer_scoped)
    print(json.dumps({
        "overall_metrics": report["overall_metrics"],
        "per_insurer_metrics": report["per_insurer_metrics"],
        "failed_hit_at_5": report["failed_hit_at_5"],
        "incorrect_insurer_retrieval_count": report["incorrect_insurer_retrieval_count"],
        "missing_metadata_result_count": report["missing_metadata_result_count"],
    }, indent=2, ensure_ascii=False))
