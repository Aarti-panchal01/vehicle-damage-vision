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


class FakeCollection:
    def __init__(self, ids, metadata):
        self.ids = ids
        self.metadata = metadata
        self.last_where = None

    def query(self, query_embeddings, n_results, where, include):
        self.last_where = where
        candidates = [
            chunk_id for chunk_id, metadata in zip(self.ids, self.metadata)
            if not where or metadata["insurer"] == where.get("insurer")
        ]
        return {"ids": [candidates[:n_results]]}


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
    retriever.collection = FakeCollection(retriever.ids, retriever.metadatas)
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
    assert retriever.collection.last_where == {"insurer": "ACKO"}
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
