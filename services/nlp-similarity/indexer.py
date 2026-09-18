"""
indexer.py
==========
Vector similarity index for MPLADS project descriptions.

Features:
- SentenceTransformer embeddings (default: all-MiniLM-L6-v2)
- Fast in-memory FAISS IndexFlatIP (cosine similarity via unit normalization)
- Resilient fallback to numpy dot-product if FAISS is not present
- PostgreSQL batch-loading from mplads_project table
- Direct record loading for unit tests and offline evaluation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    faiss = None
    HAS_FAISS = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    SentenceTransformer = None
    HAS_SENTENCE_TRANSFORMERS = False

from cleaner import clean_work_description
from models import SimilarProject, SimilarProjectsResponse
from reasoning import generate_similarity_reason

log = logging.getLogger("nlp_similarity.indexer")

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class NLPSimilarityIndex:
    """
    Maintains embeddings, FAISS/numpy index, and metadata for MPLADS project descriptions.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.device = device or "cpu"
        self._model: Any = None

        # Data stores
        self.project_ids: List[str] = []
        self.id_to_idx: Dict[str, int] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Optional[np.ndarray] = None

        # Index
        self.faiss_index: Any = None
        self._is_loaded: bool = False

    def _get_model(self) -> Any:
        """Lazy load SentenceTransformer model."""
        if self._model is None:
            if not HAS_SENTENCE_TRANSFORMERS:
                raise RuntimeError(
                    "sentence-transformers is not installed. Please install sentence-transformers."
                )
            log.info("Loading SentenceTransformer model '%s' on %s...", self.model_name, self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
            log.info("Model loaded successfully.")
        return self._model

    def encode_texts(self, texts: List[str], batch_size: int = 256) -> np.ndarray:
        """
        Generate L2-normalized embeddings for a list of cleaned texts.
        """
        model = self._get_model()
        # SentenceTransformers encode supports normalize_embeddings=True
        emb = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 500,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return emb.astype(np.float32)

    def load_from_records(
        self,
        records: List[Dict[str, Any]],
        batch_size: int = 256,
        precomputed_embeddings: Optional[np.ndarray] = None,
    ) -> int:
        """
        Load projects from a list of record dicts.
        Each record should contain:
          - id: str
          - work: str (raw or cleaned)
          - state: Optional[str]
          - constituency: Optional[str]
          - block: Optional[str]
          - village: Optional[str]
          - allocation_amount: Optional[float]
        """
        if not records:
            log.warning("No records provided to load_from_records.")
            self._is_loaded = True
            return 0

        log.info("Processing %d project records...", len(records))

        cleaned_records = []
        texts_to_encode = []

        for rec in records:
            p_id = str(rec["id"])
            raw_w = rec.get("work") or ""
            cleaned_w = clean_work_description(raw_w)
            # Ensure text is not empty for embedding
            effective_text = cleaned_w if cleaned_w else (raw_w.strip() or "infrastructure project")

            meta = {
                "id": p_id,
                "raw_work": raw_w,
                "cleaned_work": cleaned_w,
                "state": rec.get("state"),
                "constituency": rec.get("constituency"),
                "block": rec.get("block"),
                "village": rec.get("village"),
                "allocation_amount": (
                    float(rec["allocation_amount"])
                    if rec.get("allocation_amount") is not None
                    else None
                ),
            }
            cleaned_records.append(meta)
            texts_to_encode.append(effective_text)

        if precomputed_embeddings is not None:
            embeddings = precomputed_embeddings.astype(np.float32)
            # Ensure L2 normalization
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings = embeddings / norms
        else:
            embeddings = self.encode_texts(texts_to_encode, batch_size=batch_size)

        # Store metadata
        self.project_ids = [r["id"] for r in cleaned_records]
        self.id_to_idx = {pid: i for i, pid in enumerate(self.project_ids)}
        self.metadata = {r["id"]: r for r in cleaned_records}
        self.embeddings = embeddings

        # Build FAISS index if available
        dim = embeddings.shape[1]
        if HAS_FAISS:
            log.info("Building FAISS IndexFlatIP (dim=%d) for %d vectors...", dim, len(self.project_ids))
            self.faiss_index = faiss.IndexFlatIP(dim)
            self.faiss_index.add(embeddings)
            log.info("FAISS index built successfully.")
        else:
            log.info("FAISS not available; falling back to vectorized numpy cosine search.")
            self.faiss_index = None

        self._is_loaded = True
        return len(self.project_ids)

    def load_from_db(
        self,
        db_url: str,
        batch_size: int = 256,
        limit: Optional[int] = None,
    ) -> int:
        """
        Load real project descriptions from PostgreSQL table mplads_project.
        """
        import psycopg2
        import psycopg2.extras

        log.info("Connecting to DB: %s", db_url.split("@")[-1] if "@" in db_url else db_url)
        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = """
                    SELECT id, work, state, constituency, block, village, allocation_amount
                    FROM mplads_project
                    WHERE work IS NOT NULL AND TRIM(work) != ''
                    ORDER BY id
                """
                if limit:
                    query += f" LIMIT {int(limit)}"

                cur.execute(query)
                rows = cur.fetchall()
                log.info("Fetched %d rows from mplads_project.", len(rows))
        finally:
            conn.close()

        records = [dict(row) for row in rows]
        return self.load_from_records(records, batch_size=batch_size)

    def get_similar(
        self,
        project_id: str,
        top_k: int = 5,
    ) -> SimilarProjectsResponse:
        """
        Find the top_k most similar projects by WORK description for the given project_id.
        Excludes the project itself from results.
        """
        if not self._is_loaded or self.embeddings is None:
            raise RuntimeError("Similarity index is not yet initialized or loaded.")

        p_id = str(project_id)
        if p_id not in self.id_to_idx:
            raise KeyError(f"Project ID '{project_id}' not found in index.")

        query_idx = self.id_to_idx[p_id]
        query_meta = self.metadata[p_id]
        q_emb = self.embeddings[query_idx:query_idx + 1]  # shape: (1, dim)

        # Request top_k + 1 to account for self match
        fetch_k = min(top_k + 1, len(self.project_ids))

        if self.faiss_index is not None:
            distances, indices = self.faiss_index.search(q_emb, fetch_k)
            scores = distances[0]
            cand_indices = indices[0]
        else:
            # Vectorized numpy dot product on unit normalized vectors
            sims = np.dot(self.embeddings, q_emb.T).flatten()
            cand_indices = np.argpartition(-sims, fetch_k - 1)[:fetch_k]
            cand_indices = cand_indices[np.argsort(-sims[cand_indices])]
            scores = sims[cand_indices]

        similar_projects: List[SimilarProject] = []

        q_state = query_meta.get("state")
        q_const = query_meta.get("constituency")
        q_block = query_meta.get("block")
        q_village = query_meta.get("village")
        q_alloc = query_meta.get("allocation_amount")

        for score, idx in zip(scores, cand_indices):
            cand_id = self.project_ids[idx]
            if cand_id == p_id:
                # Exclude query project itself
                continue

            target_meta = self.metadata[cand_id]
            t_state = target_meta.get("state")
            t_const = target_meta.get("constituency")
            t_block = target_meta.get("block")
            t_village = target_meta.get("village")
            t_alloc = target_meta.get("allocation_amount")

            # Evaluate geographical similarities
            same_state = bool(
                q_state and t_state and q_state.strip().lower() == t_state.strip().lower()
            )
            same_const = bool(
                q_const and t_const and q_const.strip().lower() == t_const.strip().lower()
            )

            # Village or block match where available
            village_match = bool(
                q_village and t_village and q_village.strip().lower() == t_village.strip().lower()
            )
            block_match = bool(
                q_block and t_block and q_block.strip().lower() == t_block.strip().lower()
            )
            same_village_or_block = village_match or block_match

            # Allocation difference
            if q_alloc is not None and t_alloc is not None:
                alloc_diff = round(abs(float(q_alloc) - float(t_alloc)), 2)
            else:
                alloc_diff = None

            # Generate similarity reason
            q_clean = query_meta.get("cleaned_work") or query_meta.get("raw_work") or ""
            t_clean = target_meta.get("cleaned_work") or target_meta.get("raw_work") or ""
            sim_score = max(0.0, min(1.0, float(score)))

            reason = generate_similarity_reason(q_clean, t_clean, sim_score)

            similar_projects.append(
                SimilarProject(
                    similar_project_id=cand_id,
                    similarity_score=round(sim_score, 4),
                    similarity_reason=reason,
                    same_state=same_state,
                    same_constituency=same_const,
                    same_village_or_block=same_village_or_block,
                    allocation_difference=alloc_diff,
                    similar_project_work=t_clean,
                    similar_state=t_state,
                    similar_constituency=t_const,
                    similar_block=t_block,
                    similar_village=t_village,
                    similar_allocation_amount=t_alloc,
                )
            )

            if len(similar_projects) >= top_k:
                break

        return SimilarProjectsResponse(
            project_id=p_id,
            raw_work=query_meta.get("raw_work"),
            cleaned_work=query_meta.get("cleaned_work") or "",
            state=q_state,
            constituency=q_const,
            block=q_block,
            village=q_village,
            allocation_amount=q_alloc,
            similar_projects=similar_projects,
            total_found=len(similar_projects),
        )

    def summary(self) -> Dict[str, Any]:
        """Return diagnostic metrics for /health endpoint."""
        dim = self.embeddings.shape[1] if self.embeddings is not None else EMBEDDING_DIM
        backend = "faiss" if (self.faiss_index is not None) else "numpy_fallback"
        return {
            "status": "ok" if self._is_loaded else "degraded",
            "service": "nlp-similarity",
            "model_name": self.model_name,
            "index_size": len(self.project_ids),
            "embedding_dimension": dim,
            "index_backend": backend,
            "is_ready": self._is_loaded,
        }
