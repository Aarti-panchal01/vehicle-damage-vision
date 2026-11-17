"""
Hybrid insurance-policy retriever.

Components:
- BGE-small semantic embeddings
- Local NumPy cosine-similarity index
- BM25 lexical retrieval
- Reciprocal Rank Fusion (RRF)
- Insurer and UIN metadata filtering
- Page-level evidence provenance

Python 3.9 compatible.
"""

import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


ROOT_DIR = Path(__file__).resolve().parents[2]

CHUNK_PATH = ROOT_DIR / "data" / "processed" / "clause_aware_chunks.jsonl"
VECTOR_DB_PATH = ROOT_DIR / "data" / "vector_db"
VECTOR_INDEX_FILENAME = "policy_embeddings.npz"

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

BATCH_SIZE = 32
DEFAULT_TOP_K = 5
BM25_CANDIDATES = 15
VECTOR_CANDIDATES = 15
RRF_K = 60


def tokenize(text: str) -> List[str]:
    """Tokenize text for BM25."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


# Insurance terminology expansion.
# These are search synonyms, not policy conclusions.
QUERY_EXPANSIONS = {
    "alcohol": "intoxicating liquor",
    "drunk": "intoxicating liquor",
    "drunken": "intoxicating liquor",
    "driving under influence": "under the influence",
    "under influence": "under the influence",
    "vehicle damage": "accidental loss or damage to the vehicle insured",
    "car damage": "accidental loss or damage to the vehicle insured",
    "owner permission": "knowledge and consent of the Insured",
    "owner consent": "knowledge and consent of the Insured",
    "driving licence": "effective driving license valid driving license",
    "license": "licence",
    "theft": "burglary housebreaking theft",
    "flood": "flood inundation storm tempest cyclone",
    "depreciation": "depreciation deduction replaced parts age of vehicle",
    "wear and tear": "wear and tear mechanical or electrical breakdown",
}


def expand_insurance_query(query):
    """
    Add policy-language synonyms to a natural-language query.

    Original wording is retained. Expansion terms only improve
    retrieval recall and must never be treated as evidence.
    """
    normalized = query.lower()
    additions = []

    for phrase, expansion in QUERY_EXPANSIONS.items():
        if phrase in normalized:
            additions.append(expansion)

    if not additions:
        return query

    return query + " " + " ".join(additions)



def query_policy_scope(query: str) -> Optional[str]:
    """Infer the policy section most relevant to a retrieval query."""
    text = " ".join(query.casefold().replace("-", " ").split())

    if any(term in text for term in (
        "third party", "third parties", "third party liability",
        "liability to third parties", "third party property",
    )):
        return "third_party"

    if any(term in text for term in (
        "personal accident", "owner driver", "unnamed passenger",
        "paid driver", "bodily injury", "passenger compensation",
    )):
        return "personal_accident"

    if any(term in text for term in (
        "add on", "engine protect", "zero depreciation",
        "return to invoice", "roadside assistance", "consumables",
        "key replacement", "electrical electronic fittings",
        "personal belongings", "tyre protect", "rim protect",
    )):
        return "add_on"

    if any(term in text for term in (
        "own damage", "vehicle is damaged", "vehicle damage",
        "damage to the vehicle", "loss or damage to the vehicle",
        "accidental loss", "depreciation", "replaced parts",
        "wear and tear", "intoxicating liquor", "under the influence",
        "under influence", "alcohol", "drugs", "drunk",
        "flood", "theft", "fire",
    )):
        return "own_damage"

    return None


class HybridPolicyRetriever:
    """Retrieve policy clauses using vector and keyword search."""

    def __init__(
        self,
        chunk_path: Path = CHUNK_PATH,
        db_path: Path = VECTOR_DB_PATH,
        model_name: str = EMBEDDING_MODEL_NAME,
    ):
        self.chunk_path = Path(chunk_path)
        self.db_path = Path(db_path)
        self.model_name = model_name

        self.model = SentenceTransformer(model_name)

        self.documents: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.ids: List[str] = []
        self.embeddings: Optional[np.ndarray] = None

        self.bm25 = None
        self.bm25_tokens: List[List[str]] = []

        self.initialized = False

    def load_chunks(self) -> List[Dict[str, Any]]:
        """Read and validate the generated chunk JSONL file."""
        if not self.chunk_path.exists():
            raise FileNotFoundError(
                "Chunk file not found: {}".format(self.chunk_path)
            )

        chunks = []

        with self.chunk_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "Invalid JSON on line {}: {}".format(
                            line_number, exc
                        )
                    )

                text = chunk.get("text", "").strip()
                metadata = chunk.get("metadata", {})

                if not text:
                    continue

                chunk_id = metadata.get("chunk_id")

                if not chunk_id:
                    raise ValueError(
                        "Chunk missing chunk_id on line {}".format(
                            line_number
                        )
                    )

                required = ["insurer", "file_name", "page"]

                missing = [
                    key for key in required
                    if metadata.get(key) is None
                ]

                if missing:
                    raise ValueError(
                        "Chunk {} missing metadata: {}".format(
                            chunk_id, missing
                        )
                    )

                chunks.append(chunk)

        if not chunks:
            raise ValueError("No usable chunks found.")

        ids = [
            str(c["metadata"]["chunk_id"]) for c in chunks
        ]

        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate chunk IDs found.")

        return chunks

    def set_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Set the canonical documents, metadata, and IDs used by both indexes."""
        self.documents = [chunk["text"] for chunk in chunks]
        self.metadatas = [
            dict(chunk["metadata"]) for chunk in chunks
        ]
        self.ids = [
            str(chunk["metadata"]["chunk_id"]) for chunk in chunks
        ]

    @property
    def vector_index_path(self) -> Path:
        return self.db_path / VECTOR_INDEX_FILENAME

    @staticmethod
    def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
        """Validate and normalize dense vectors for cosine similarity."""
        matrix = np.asarray(embeddings, dtype=np.float32)
        if matrix.ndim != 2 or not matrix.shape[0] or not matrix.shape[1]:
            raise ValueError("Embedding matrix must be a non-empty 2D array.")
        if not np.isfinite(matrix).all():
            raise ValueError("Embedding matrix contains non-finite values.")

        norms = np.linalg.norm(matrix, axis=1)
        if np.any(norms == 0):
            raise ValueError("Embedding matrix contains a zero-length vector.")
        return matrix / norms[:, np.newaxis]

    def save_vector_index(self) -> None:
        """Persist normalized vectors in a non-pickle NumPy archive."""
        if self.embeddings is None:
            raise RuntimeError("Cannot save an unbuilt vector index.")

        self.db_path.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.db_path,
                prefix="policy-embeddings-",
                suffix=".npz.tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                np.savez_compressed(
                    temporary_file,
                    ids=np.asarray(self.ids, dtype=np.str_),
                    embeddings=self.embeddings,
                )
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, self.vector_index_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def rebuild_index(self) -> int:
        """
        Rebuild the vector index from the canonical JSONL chunks.

        Vectors are written as an atomic local NumPy archive.
        """
        chunks = self.load_chunks()
        self.set_chunks(chunks)

        print("Building BGE embeddings...")

        embedding_batches = []
        for start in range(0, len(chunks), BATCH_SIZE):
            end = min(start + BATCH_SIZE, len(chunks))

            batch_texts = self.documents[start:end]
            embeddings = np.asarray(self.model.encode(
                batch_texts,
                batch_size=BATCH_SIZE,
                normalize_embeddings=True,
                show_progress_bar=False,
            ), dtype=np.float32)
            if embeddings.ndim != 2 or embeddings.shape[0] != len(batch_texts):
                raise ValueError("Embedding model returned an invalid batch shape.")
            embedding_batches.append(embeddings)

            print(
                "Indexed {}/{} chunks".format(end, len(chunks))
            )

        self.embeddings = self.normalize_embeddings(
            np.concatenate(embedding_batches, axis=0)
        )
        self.save_vector_index()
        self.build_bm25()

        self.initialized = True

        return len(chunks)

    def build_bm25(self) -> None:
        """Build the lexical search index."""
        self.bm25_tokens = [
            tokenize(document)
            for document in self.documents
        ]

        self.bm25 = BM25Okapi(self.bm25_tokens)

    def load_existing_index(self) -> bool:
        """
        Load a safe NumPy vector cache and rebuild BM25 from canonical chunks.
        """
        index_path = self.vector_index_path
        if not index_path.is_file():
            return False

        chunks = self.load_chunks()
        self.set_chunks(chunks)

        try:
            with np.load(index_path, allow_pickle=False) as stored:
                stored_ids = stored["ids"].tolist()
                embeddings = stored["embeddings"]
        except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as exc:
            print("Vector cache is invalid ({}); rebuilding.".format(exc))
            return False

        if stored_ids != self.ids:
            print("Vector cache IDs do not match canonical chunks; rebuilding.")
            return False

        try:
            self.embeddings = self.normalize_embeddings(embeddings)
        except ValueError as exc:
            print("Vector cache is invalid ({}); rebuilding.".format(exc))
            return False

        if self.embeddings.shape[0] != len(self.ids):
            self.embeddings = None
            print("Vector cache size does not match canonical chunks; rebuilding.")
            return False

        self.build_bm25()
        self.initialized = True

        return True

    def initialize(self, rebuild: bool = False) -> None:
        """Initialize vector and BM25 indexes."""
        if rebuild:
            count = self.rebuild_index()
            print("Index rebuilt: {} chunks.".format(count))
            return

        if self.load_existing_index():
            print(
                "Existing index loaded: {} chunks.".format(
                    len(self.documents)
                )
            )
        else:
            count = self.rebuild_index()
            print("Index created: {} chunks.".format(count))

    @staticmethod
    def metadata_matches(
        metadata: Dict[str, Any],
        insurer: Optional[str] = None,
        uin: Optional[str] = None,
    ) -> bool:
        """Apply exact insurer and UIN filters."""
        if insurer:
            if str(metadata.get("insurer", "")).casefold() != insurer.casefold():
                return False

        if uin:
            if str(metadata.get("uin", "")).casefold() != uin.casefold():
                return False

        return True

    def retrieve(
        self,
        query: str,
        insurer: Optional[str] = None,
        uin: Optional[str] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> List[Dict[str, Any]]:
        """Run BM25 + vector search followed by RRF."""
        if not self.initialized:
            raise RuntimeError(
                "Retriever is not initialized. Call initialize() first."
            )

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        # Fail closed: never silently mix insurers.
        if insurer or uin:
            available = [
                metadata
                for metadata in self.metadatas
                if self.metadata_matches(
                    metadata, insurer=insurer, uin=uin
                )
            ]

            if not available:
                raise ValueError(
                    "No policy documents match the requested "
                    "insurer/UIN filter."
                )

        eligible_indices = [
            i for i, metadata in enumerate(self.metadatas)
            if self.metadata_matches(
                metadata, insurer=insurer, uin=uin
            )
        ]

        if not eligible_indices:
            return []

        expanded_query = expand_insurance_query(query)
        query_tokens = tokenize(expanded_query)

        bm25_scores = self.bm25.get_scores(query_tokens)

        bm25_ranked = sorted(
            eligible_indices,
            key=lambda i: float(bm25_scores[i]),
            reverse=True,
        )[:BM25_CANDIDATES]

        bm25_rank = {
            index: rank
            for rank, index in enumerate(bm25_ranked, start=1)
        }

        query_embedding = np.asarray(self.model.encode(
            ["Represent this sentence for searching relevant passages: " + expanded_query],
            normalize_embeddings=True,
        )[0], dtype=np.float32).reshape(-1)
        if self.embeddings is None:
            raise RuntimeError("Vector index is missing. Rebuild the index.")
        if self.embeddings.shape[1] != query_embedding.size:
            raise ValueError("Query and document embedding dimensions do not match.")

        query_norm = np.linalg.norm(query_embedding)
        if not np.isfinite(query_norm) or query_norm == 0:
            raise ValueError("Query embedding is not a valid vector.")
        query_embedding /= query_norm

        similarities = self.embeddings @ query_embedding
        vector_ranked = sorted(
            eligible_indices,
            key=lambda i: (-float(similarities[i]), self.ids[i]),
        )[:min(VECTOR_CANDIDATES, len(eligible_indices))]

        vector_rank = {
            self.ids[index]: rank
            for rank, index in enumerate(vector_ranked, start=1)
        }

        index_by_id = {
            chunk_id: i
            for i, chunk_id in enumerate(self.ids)
        }

        candidate_ids = set(
            self.ids[i] for i in bm25_ranked
        )
        candidate_ids.update(vector_rank)

        desired_scope = query_policy_scope(query)
        fused = []

        for chunk_id in candidate_ids:
            index = index_by_id[chunk_id]
            score = 0.0

            if index in bm25_rank:
                score += 1.0 / (RRF_K + bm25_rank[index])

            if chunk_id in vector_rank:
                score += 1.0 / (RRF_K + vector_rank[chunk_id])

            actual_scope = self.metadatas[index].get(
                "policy_scope", "general"
            )
            scope_match = (
                desired_scope is not None
                and actual_scope == desired_scope
            )
            scope_bonus = 0.01 if scope_match else 0.0
            clause_bonus = 0.0

            normalized_text = " ".join(
                self.documents[index].casefold().split()
            )
            query_mentions_intoxication = any(
                term in query.casefold()
                for term in ("alcohol", "drugs", "drunk", "intoxicating liquor")
            )

            if desired_scope == "own_damage" and query_mentions_intoxication:
                has_intoxication_wording = (
                    "intoxicating liquor" in normalized_text
                    and "under the influence" in normalized_text
                )

                has_vehicle_damage_exclusion = (
                    any(phrase in normalized_text for phrase in (
                        "accidental loss or damage suffered whilst",
                        "accidental loss or damage suffered while",
                        "accidental loss or damage whilst",
                        "accidental loss or damage while",
                    ))
                    and "knowledge and consent" in normalized_text
                )

                has_personal_accident_wording = any(
                    phrase in normalized_text
                    for phrase in (
                        "bodily injury",
                        "death or injury",
                        "scale of compensation",
                        "compensation shall be payable",
                        "personal accident",
                        "paid driver",
                        "unnamed passengers",
                    )
                )

                if has_intoxication_wording and has_vehicle_damage_exclusion:
                    clause_bonus = 0.04
                elif has_intoxication_wording and has_personal_accident_wording:
                    clause_bonus = -0.025

            ranking_score = score + scope_bonus + clause_bonus

            fused.append((
                chunk_id, score, ranking_score, index, scope_match
            ))

        # Prefer the intended policy section, then hybrid relevance.
        # Chunk ID provides deterministic tie-breaking.
        fused.sort(
            key=lambda item: (
                -item[2], -item[1], item[0]
            )
        )

        results = []

        for chunk_id, score, ranking_score, index, scope_match in fused[:top_k]:
            metadata = dict(self.metadatas[index])

            results.append({
                "chunk_id": chunk_id,
                "text": self.documents[index],
                "metadata": metadata,
                "hybrid_score": round(score, 6),
                "ranking_score": round(ranking_score, 6),
                "scope_match": scope_match,
                "matched_policy_scope": metadata.get("policy_scope"),
                "citation": {
                    "insurer": metadata.get("insurer"),
                    "document": metadata.get("document_name"),
                    "file_name": metadata.get("file_name"),
                    "page": metadata.get("page"),
                    "source_url": metadata.get("source_url"),
                    "uin": metadata.get("uin"),
                },
            })

        return results


def main():
    """Build the index and run a retrieval smoke test."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Hybrid insurance policy retriever"
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the persistent vector index",
    )

    parser.add_argument(
        "--query",
        type=str,
        default="What depreciation applies to replaced vehicle parts?",
    )

    parser.add_argument(
        "--insurer",
        type=str,
        default=None,
    )

    parser.add_argument(
        "--uin",
        type=str,
        default=None,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    retriever = HybridPolicyRetriever()
    retriever.initialize(rebuild=args.rebuild)

    results = retriever.retrieve(
        query=args.query,
        insurer=args.insurer,
        uin=args.uin,
        top_k=args.top_k,
    )

    print("\nRETRIEVAL RESULTS")
    print("=" * 65)

    for rank, result in enumerate(results, start=1):
        citation = result["citation"]

        print(
            "\n{}. {} | Page {} | Score {}".format(
                rank,
                citation["insurer"],
                citation["page"],
                result["hybrid_score"],
            )
        )

        print("Document:", citation["document"])
        print("UIN:", citation["uin"])
        print("Chunk ID:", result["chunk_id"])
        print("Text:", result["text"][:700])


if __name__ == "__main__":
    main()
