import json

import numpy as np
import pytest

from src.rag.evaluate_retrieval import is_relevant, summarize
from src.rag.retriever import HybridPolicyRetriever


def test_relevance_requires_exact_policy_page_and_section():
    record = {
        "insurer": "Example Insurer",
        "policy_uin": "UIN-1",
        "expected_sources": [{
            "page_number": 7,
            "policy_section": "Claims Procedure",
        }],
    }
    result = {"metadata": {
        "insurer": "Example Insurer",
        "uin": "UIN-1",
        "page": 7,
        "policy_section": "Claims Procedure",
    }}
    assert is_relevant(result, record)

    result["metadata"]["policy_section"] = "General Policy Conditions"
    assert not is_relevant(result, record)
    result["metadata"]["policy_section"] = "Claims Procedure"
    result["metadata"]["uin"] = "UIN-2"
    assert not is_relevant(result, record)


def test_metrics_use_first_exact_hit_rank():
    records = [
        {"relevant_ranks": [2, 4]},
        {"relevant_ranks": []},
    ]
    assert summarize(records) == {
        "question_count": 2,
        "hit_at_1": 0.0,
        "hit_at_3": 0.5,
        "hit_at_5": 0.5,
        "mrr_at_5": 0.25,
    }


class FakeBM25:
    def get_scores(self, _tokens):
        return np.array([4.0, 3.0, 2.0, 1.0])


class FakeModel:
    def encode(self, _texts, normalize_embeddings=True):
        return np.array([[0.1, 0.2]])


def make_retriever():
    retriever = object.__new__(HybridPolicyRetriever)
    retriever.initialized = True
    retriever.documents = ["coverage clause"] * 4
    retriever.metadatas = [
        {"insurer": "ACKO", "uin": "A", "page": 1, "policy_scope": "general"},
        {"insurer": "ACKO", "uin": "A", "page": 2, "policy_scope": "general"},
        {"insurer": "HDFC ERGO", "uin": "H", "page": 1, "policy_scope": "general"},
        {"insurer": "SBI General", "uin": "S", "page": 1, "policy_scope": "general"},
    ]
    retriever.ids = ["a1", "a2", "h1", "s1"]
    retriever.bm25 = FakeBM25()
    retriever.model = FakeModel()
    retriever.embeddings = HybridPolicyRetriever.normalize_embeddings(
        np.array([
            [-0.1, -0.2],
            [-0.2, -0.1],
            [0.1, 0.2],
            [0.2, 0.1],
        ])
    )
    return retriever


def insurers(results):
    return {result["metadata"]["insurer"] for result in results}


def test_acko_scope_returns_only_acko():
    retriever = make_retriever()
    assert insurers(retriever.retrieve("coverage", insurer="ACKO")) == {"ACKO"}


def test_hdfc_scope_returns_only_hdfc():
    retriever = make_retriever()
    assert insurers(retriever.retrieve("coverage", insurer="HDFC ERGO")) == {"HDFC ERGO"}


def test_vector_and_bm25_candidates_both_use_insurer_filter():
    retriever = make_retriever()
    results = retriever.retrieve("coverage", insurer="ACKO")
    assert insurers(results) == {"ACKO"}
    assert {result["chunk_id"] for result in results} == {"a1", "a2"}


def test_unknown_insurer_raises_clear_validation_error():
    with pytest.raises(ValueError, match="No policy documents match"):
        make_retriever().retrieve("coverage", insurer="Unknown Carrier")


def test_omitting_insurer_preserves_cross_insurer_search():
    results = make_retriever().retrieve("coverage")
    assert insurers(results) == {"ACKO", "HDFC ERGO", "SBI General"}


def test_existing_positional_retrieve_call_remains_compatible():
    results = make_retriever().retrieve("coverage", None, None, 2)
    assert len(results) == 2


def write_chunks(path, chunk_ids):
    chunks = [
        {
            "text": "Coverage includes accidental damage.",
            "metadata": {
                "chunk_id": chunk_id,
                "insurer": "ACKO",
                "file_name": "policy.pdf",
                "page": page,
                "policy_scope": "own_damage",
            },
        }
        for page, chunk_id in enumerate(chunk_ids, start=1)
    ]
    path.write_text(
        "\n".join(json.dumps(chunk) for chunk in chunks) + "\n",
        encoding="utf-8",
    )


def make_cache_reader(tmp_path, chunk_ids):
    chunk_path = tmp_path / "chunks.jsonl"
    write_chunks(chunk_path, chunk_ids)
    retriever = object.__new__(HybridPolicyRetriever)
    retriever.chunk_path = chunk_path
    retriever.db_path = tmp_path / "vectors"
    retriever.initialized = False
    retriever.documents = []
    retriever.metadatas = []
    retriever.ids = []
    retriever.embeddings = None
    retriever.bm25 = None
    retriever.bm25_tokens = []
    return retriever


def test_vector_cache_round_trip_uses_canonical_chunk_ids(tmp_path):
    chunk_ids = ["chunk-1", "chunk-2"]
    writer = make_cache_reader(tmp_path, chunk_ids)
    writer.ids = chunk_ids
    writer.embeddings = HybridPolicyRetriever.normalize_embeddings(
        np.array([[1.0, 0.0], [0.0, 1.0]])
    )
    writer.save_vector_index()

    reader = make_cache_reader(tmp_path, chunk_ids)
    assert reader.load_existing_index()
    assert reader.ids == chunk_ids
    assert reader.initialized
    np.testing.assert_allclose(reader.embeddings, writer.embeddings)


def test_vector_cache_rejects_pickled_object_arrays(tmp_path):
    chunk_ids = ["chunk-1"]
    retriever = make_cache_reader(tmp_path, chunk_ids)
    retriever.db_path.mkdir()
    np.savez_compressed(
        retriever.vector_index_path,
        ids=np.asarray(chunk_ids, dtype=object),
        embeddings=np.array([[1.0, 0.0]]),
    )

    assert not retriever.load_existing_index()
    assert not retriever.initialized
