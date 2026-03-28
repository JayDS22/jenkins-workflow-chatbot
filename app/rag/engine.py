"""
RAG Engine - Retrieval Augmented Generation over Jenkins documentation.

This adds a knowledge layer on top of the context-aware agents.
The agents already read live Jenkins state (jobs, logs, plugins).
Now they can ALSO retrieve relevant documentation to back up their answers.

How it works:
  1. On startup, we load a curated corpus of Jenkins documentation
  2. Each doc chunk gets embedded using sentence-transformers (all-MiniLM-L6-v2)
  3. Embeddings are stored in a FAISS index for fast similarity search
  4. When an agent handles a query, it can retrieve the top-k most relevant
     doc chunks and include them as additional context in its prompt

This is the same pattern as the existing resources-ai-chatbot-plugin's
retriever, but lighter weight and focused on the most common Jenkins topics.
In the full GSoC project, this would scale to the entire Jenkins doc corpus
plus Discourse threads and Stack Overflow answers.

The embedding model (all-MiniLM-L6-v2) is only 80MB and runs on CPU.
No GPU needed, loads in seconds, and gives solid retrieval quality.
"""

import json
import os
import logging
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Track whether heavy dependencies are available
# This lets the app still run if sentence-transformers or faiss aren't installed
_FAISS_AVAILABLE = False
_ST_AVAILABLE = False

try:
    import faiss
    _FAISS_AVAILABLE = True
except ImportError:
    logger.warning("faiss-cpu not installed - RAG will use keyword fallback")

try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers not installed - RAG will use keyword fallback")


class JenkinsRAG:
    """
    Retrieval engine over Jenkins documentation.

    Supports two modes:
      1. Vector search (FAISS + sentence-transformers) - used when dependencies are available
      2. Keyword fallback - simple TF-IDF-style matching when dependencies are missing

    This dual-mode approach means the PoC runs everywhere, even if someone
    doesn't want to install the ML dependencies. The vector search is obviously
    better, but the keyword fallback still returns useful results.
    """

    def __init__(self, corpus_path: Optional[str] = None):
        if corpus_path is None:
            # Default to the bundled corpus
            corpus_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "jenkins_docs", "corpus.json"
            )

        self.corpus = []
        self.index = None
        self.model = None
        self._ready = False

        self._load_corpus(corpus_path)

    def _load_corpus(self, corpus_path: str):
        """Load the document corpus from JSON."""
        try:
            with open(corpus_path, "r") as f:
                self.corpus = json.load(f)
            logger.info(f"Loaded {len(self.corpus)} Jenkins doc chunks")
        except FileNotFoundError:
            logger.warning(f"Corpus not found at {corpus_path} - RAG disabled")
            return
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse corpus JSON: {e}")
            return

        if _FAISS_AVAILABLE and _ST_AVAILABLE:
            self._build_vector_index()
        else:
            logger.info("Running RAG in keyword-fallback mode (no FAISS/sentence-transformers)")
            self._ready = True

    def _build_vector_index(self):
        """
        Build the FAISS index from the corpus using sentence-transformers.

        We use all-MiniLM-L6-v2 because it's:
          - Small (80MB download, ~100MB in memory)
          - Fast (encodes in milliseconds on CPU)
          - Good quality (competitive with much larger models for retrieval)
          - The same model the existing resources-ai-chatbot-plugin uses
        """
        try:
            logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

            # Combine title + content for richer embeddings
            texts = [
                f"{doc['title']}: {doc['content']}"
                for doc in self.corpus
            ]

            logger.info(f"Encoding {len(texts)} document chunks...")
            embeddings = self.model.encode(texts, show_progress_bar=False)
            embeddings = np.array(embeddings).astype("float32")

            # Normalize for cosine similarity
            faiss.normalize_L2(embeddings)

            # Build the index - simple flat index is fine for <1000 docs
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)  # Inner product on normalized = cosine
            self.index.add(embeddings)

            self._ready = True
            logger.info(f"FAISS index built: {self.index.ntotal} vectors, {dimension}d")

        except Exception as e:
            logger.error(f"Failed to build vector index: {e}")
            # Fall back to keyword mode
            self._ready = True

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Retrieve the most relevant doc chunks for a query.

        Returns a list of dicts with title, source, content, and relevance score.
        Uses vector search when available, keyword matching as fallback.
        """
        if not self._ready or not self.corpus:
            return []

        if self.index is not None and self.model is not None:
            return self._vector_search(query, top_k)
        else:
            return self._keyword_search(query, top_k)

    def _vector_search(self, query: str, top_k: int) -> list[dict]:
        """Semantic search using FAISS + sentence-transformers."""
        try:
            query_embedding = self.model.encode([query])
            query_embedding = np.array(query_embedding).astype("float32")
            faiss.normalize_L2(query_embedding)

            scores, indices = self.index.search(query_embedding, min(top_k, len(self.corpus)))

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self.corpus):
                    continue
                doc = self.corpus[idx]
                results.append({
                    "title": doc["title"],
                    "source": doc["source"],
                    "content": doc["content"],
                    "score": float(score),
                })

            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        """
        Simple keyword-based search as a fallback.

        Counts how many query words appear in each document.
        Not as good as vector search, but works without any ML dependencies
        and still returns relevant results for common Jenkins queries.
        """
        query_words = set(query.lower().split())
        # Remove common stop words
        stop_words = {"how", "do", "i", "the", "a", "an", "is", "to", "in", "for", "what", "my", "me", "with"}
        query_words -= stop_words

        scored = []
        for doc in self.corpus:
            text = f"{doc['title']} {doc['content']}".lower()
            # Count matching words, weighted by whether they appear in title
            score = 0
            for word in query_words:
                if word in doc["title"].lower():
                    score += 3  # title matches are worth more
                if word in text:
                    score += 1

            if score > 0:
                scored.append((score, doc))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "title": doc["title"],
                "source": doc["source"],
                "content": doc["content"],
                "score": float(score),
            }
            for score, doc in scored[:top_k]
        ]

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def doc_count(self) -> int:
        return len(self.corpus)

    @property
    def using_vectors(self) -> bool:
        return self.index is not None and self.model is not None
