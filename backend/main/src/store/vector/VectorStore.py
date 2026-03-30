"""
VectorStore.py — Deep Researcher v2
=====================================
Simple async CRUD wrapper around ChromaDB for text and image storage.

- Text is chunked into 500-word paragraphs and embedded via Ollama (``embeddinggemma:latest``).
- Images are embedded via SigLIP ONNX (``imageEmbedder.SigLIPEmbedder``).
- Any collection name is accepted — ChromaDB creates it automatically if it doesn't exist.

Default collections used by this project:
    - ``research``    — research document chunks
    - ``web-scrapes`` — web-scraped page chunks
    - ``images``      — image embeddings

Quick start
-----------
::

    from main.src.store.vector.VectorStore import vector_store

    # Store text
    ids = await vector_store.add_text(
        text="Long research document...",
        collection="research",
        source_uri="https://arxiv.org/abs/xxxx",
        metadata={"author": "Smith", "year": "2024"},
    )

    # Store image
    img_id = await vector_store.add_image(
        image_path="/path/to/photo.png",
        collection="images",
        source_uri="/path/to/photo.png",
        metadata={"camera": "iPhone", "location": "NYC"},
    )

    # Search text — with optional metadata filter
    results = await vector_store.search(
        query="transformer attention mechanism",
        collection="research",
        n_results=5,
        where={"author": "Smith"},
    )

    # Search by image — with optional metadata filter
    results = await vector_store.search_by_image(
        image_path="/path/to/query.png",
        collection="images",
        n_results=5,
        where={"location": "NYC"},
    )

    # Retrieve records directly by ID
    records = await vector_store.get("images", ids=["img-abc123"])

    # Delete
    await vector_store.delete("research", ids=["txt-xyz-0"])

    # Count
    n = await vector_store.count("images")
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default collections — you can pass any string as a collection name.
# ChromaDB will create the collection automatically if it doesn't exist.
COLLECTIONS = ("research", "web-scrapes", "images")

# 500-word chunks, 50-word overlap at boundaries
CHUNK_WORDS = 500
OVERLAP_WORDS = 50

OLLAMA_MODEL = "embeddinggemma:latest"
OLLAMA_URL = "http://localhost:11434/api/embeddings"

_CHROMA_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "vector" / "chroma"
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha8(text: str) -> str:
    """
    ## Description

    Returns an 8-character SHA-256 hex digest of ``text``.
    Used to create stable, short chunk IDs from content.

    ## Parameters

    - `text` (`str`) — Any string to hash.

    ## Returns

    `str` — 8-character lowercase hex.
    """
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def _chunk_text(text: str) -> List[str]:
    """
    ## Description

    Splits ``text`` into 500-word paragraphs with a 50-word overlap so that
    context is preserved at chunk boundaries. Returns a single-element list
    when the text is shorter than one chunk.

    ## Parameters

    - `text` (`str`)
      - Description: Raw input text to split.
      - Constraints: Empty string returns ``[]``.

    ## Returns

    `List[str]` — List of word-based text chunks.
    """
    words = re.split(r"\s+", text.strip())
    if not words or words == [""]:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = start + CHUNK_WORDS
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - OVERLAP_WORDS  # slide back to create overlap

    return chunks


async def _embed_text(text: str) -> Optional[List[float]]:
    """
    ## Description

    Calls the local Ollama HTTP API to embed ``text`` using
    ``embeddinggemma:latest``. Returns ``None`` on failure.

    ## Parameters

    - `text` (`str`)
      - Description: Text to embed. Must be non-empty.

    ## Returns

    `Optional[List[float]]` — Dense embedding vector, or ``None`` on error.

    ## Side Effects

    - Makes an HTTP POST to ``OLLAMA_URL``.
    """
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": text},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                data = await resp.json()
                return data.get("embedding")
    except Exception as exc:
        _log.error(f"[VectorStore] Ollama embed failed: {exc}")
        return None


async def _embed_image(image_path: str) -> Optional[List[float]]:
    """
    ## Description

    Runs ``SigLIPEmbedder.embed()`` in a thread pool to avoid blocking
    the event loop during ONNX inference on CPU.

    ## Parameters

    - `image_path` (`str`)
      - Description: Absolute path to the image file.
      - Constraints: File must exist; supports PNG, JPEG, WEBP, GIF.
      - Example: ``r"C:\\Users\\user\\Downloads\\photo.png"``

    ## Returns

    `Optional[List[float]]` — Flat 1-D embedding vector, or ``None`` on error.

    ## Side Effects

    - Loads the SigLIP ONNX model on first call (globally cached).
    - Runs inference on the CPU thread pool.
    """
    try:
        from main.src.utils.core.ai.imageEmbedder import SigLIPEmbedder

        embedder = SigLIPEmbedder()
        result = await asyncio.to_thread(embedder.embed, image_path)

        # Guard: SigLIPEmbedder.embed() returns a 1D list, but flatten anyway
        # in case of shape variance across ONNX model versions.
        if result and isinstance(result[0], (list, tuple)):
            result = result[0]

        return [float(x) for x in result]
    except Exception as exc:
        _log.error(f"[VectorStore] SigLIP embed failed for '{image_path}': {exc}")
        return None


def _build_where(where: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    ## Description

    Converts a simple ``{key: value}`` metadata filter dict into the
    ChromaDB ``where`` clause format. ChromaDB natively accepts a simple
    equality dict for single-field filters and requires ``$and`` for
    multi-field filters in newer versions.

    This helper normalises both cases so callers always pass plain dicts.

    ## Parameters

    - `where` (`Optional[Dict[str, Any]]`)
      - Description: Simple equality filter like ``{"author": "Smith", "year": "2024"}``.
      - Constraints: All values are treated as exact-equality checks.
      - Default: ``None``

    ## Returns

    `Optional[Dict[str, Any]]` — ChromaDB-compatible ``where`` clause,
    or ``None`` if ``where`` is empty or ``None``.

    ## Example

    ```python
    _build_where({"author": "Smith", "year": "2024"})
    # Returns:
    # {"$and": [{"author": {"$eq": "Smith"}}, {"year": {"$eq": "2024"}}]}

    _build_where({"author": "Smith"})
    # Returns:
    # {"author": {"$eq": "Smith"}}

    _build_where(None)
    # Returns: None
    ```
    """
    if not where:
        return None

    clauses = [
        {k: {"$eq": v}} for k, v in where.items()
    ]

    if len(clauses) == 1:
        return clauses[0]

    return {"$and": clauses}


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------


class VectorStore:
    """
    ## Description

    Async CRUD wrapper around a ChromaDB persistent client.

    Supports:
    - **Text** ingestion: chunked into 500-word paragraphs, embedded via Ollama.
    - **Image** ingestion: embedded via SigLIP (ONNX on CPU).
    - **Metadata filtering** on all search and retrieval operations.
    - **Dynamic collections**: any collection name is accepted; ChromaDB
      creates it automatically on first use.

    The client is initialised lazily on first use, so importing this module
    has no side-effects.
    """

    def __init__(self) -> None:
        self._client = None
        self._cols: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_collection(self, name: str):
        """
        ## Description

        Returns (and lazily creates) a named ChromaDB collection.
        The collection is created with cosine distance if it doesn't exist.

        ## Parameters

        - `name` (`str`)
          - Description: Collection name — any string is accepted.
          - Example: ``"research"``

        ## Returns

        `chromadb.Collection`
        """
        if self._client is None:
            import chromadb  # type: ignore

            _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
            _log.info(f"[VectorStore] ChromaDB ready at {_CHROMA_PATH}")

        if name not in self._cols:
            self._cols[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )

        return self._cols[name]

    def _upsert_sync(
        self,
        collection: str,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """
        ## Description

        Synchronous ChromaDB upsert — runs inside ``asyncio.to_thread``.

        ## Parameters

        - `collection` (`str`) — Target collection name.
        - `ids` (`List[str]`) — Unique record IDs.
        - `embeddings` (`List[List[float]]`) — One 1-D vector per record.
        - `documents` (`List[str]`) — Raw text content per record.
        - `metadatas` (`List[Dict[str, Any]]`) — Metadata per record.

        ## Returns

        `None`
        """
        col = self._get_collection(collection)
        col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_text(
        self,
        text: str,
        collection: str = "research",
        source_uri: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        ## Description

        Chunks ``text`` into 500-word paragraphs, embeds each chunk with
        Ollama (``embeddinggemma:latest``), and upserts all vectors into the
        specified ChromaDB collection.

        The ``metadata`` dict is merged into every chunk's stored metadata
        alongside the automatic ``source`` and ``type`` fields.

        ## Parameters

        - `text` (`str`)
          - Description: Raw input text to chunk and store.
          - Constraints: Non-empty.
          - Example: ``"Transformers use self-attention to..."``

        - `collection` (`str`, optional)
          - Description: Target collection name. Created automatically if absent.
          - Default: ``"research"``
          - Example: ``"web-scrapes"``

        - `source_uri` (`str`, optional)
          - Description: Canonical identifier: URL, file path, or any string.
          - Default: ``""``
          - Example: ``"https://arxiv.org/abs/1706.03762"``

        - `metadata` (`Optional[Dict[str, Any]]`, optional)
          - Description: Extra metadata fields stored per chunk.
          - Constraints: All values must be ``str | int | float | bool``.
          - Default: ``None``
          - Example: ``{"author": "Vaswani", "year": "2017"}``

        ## Returns

        `List[str]` — Stored chunk IDs, e.g. ``["txt-a1b2c3d4-0", "txt-e5f6-1"]``.

        ## Side Effects

        - Makes HTTP calls to Ollama for each chunk.
        - Writes vectors to ChromaDB persistent store on disk.
        """
        chunks = _chunk_text(text)
        if not chunks:
            _log.warning("[VectorStore] add_text: no chunks produced.")
            return []

        base_meta = {"source": source_uri, "type": "text", **(metadata or {})}

        ids, embeddings, documents, metadatas = [], [], [], []

        for i, chunk in enumerate(chunks):
            emb = await _embed_text(chunk)
            if emb is None:
                _log.warning(f"[VectorStore] Chunk {i} skipped — embedding failed.")
                continue

            chunk_id = f"txt-{_sha8(source_uri + chunk)}-{i}"
            ids.append(chunk_id)
            embeddings.append(emb)
            documents.append(chunk)
            metadatas.append({**base_meta, "chunk_index": str(i)})

        if not ids:
            _log.error("[VectorStore] add_text: all chunks failed to embed.")
            return []

        await asyncio.to_thread(
            self._upsert_sync, collection, ids, embeddings, documents, metadatas
        )
        _log.info(
            f"[VectorStore] Stored {len(ids)} text chunks → '{collection}' from '{source_uri}'"
        )
        return ids

    async def add_image(
        self,
        image_path: str,
        collection: str = "images",
        source_uri: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        record_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        ## Description

        Embeds a single image using SigLIP (ONNX on CPU), then upserts the
        embedding vector into the specified ChromaDB collection.

        The ``metadata`` dict is merged into the stored record alongside the
        automatic ``source`` and ``type`` fields.

        ## Parameters

        - `image_path` (`str`)
          - Description: Absolute path to the image file.
          - Constraints: File must exist; supports PNG, JPEG, WEBP, GIF.
          - Example: ``r"C:\\Users\\user\\Downloads\\photo.png"``

        - `collection` (`str`, optional)
          - Description: Target collection name. Created automatically if absent.
          - Default: ``"images"``

        - `source_uri` (`str`, optional)
          - Description: Canonical source ID. Defaults to ``image_path`` if empty.
          - Default: ``""``

        - `metadata` (`Optional[Dict[str, Any]]`, optional)
          - Description: Extra metadata stored alongside the embedding.
          - Constraints: Values must be ``str | int | float | bool``.
          - Default: ``None``
          - Example: ``{"camera": "iPhone", "scene": "outdoor"}``

        - `record_id` (`Optional[str]`, optional)
          - Description: Custom ID for this record. Auto-generated from path hash if omitted.
          - Default: ``None``
          - Example: ``"my-custom-image-id-001"``

        ## Returns

        `Optional[str]` — The stored record ID, or ``None`` if embedding failed.

        ## Side Effects

        - Loads the SigLIP ONNX model on first call (globally cached).
        - Writes the vector to ChromaDB persistent store on disk.
        """
        if not source_uri:
            source_uri = image_path

        emb = await _embed_image(image_path)
        if emb is None:
            _log.error(f"[VectorStore] add_image: embedding failed for '{image_path}'.")
            return None

        img_id = record_id or f"img-{_sha8(image_path)}"
        meta = {"source": source_uri, "type": "image", **(metadata or {})}

        await asyncio.to_thread(
            self._upsert_sync,
            collection,
            [img_id],
            [emb],
            [source_uri],
            [meta],
        )
        _log.info(
            f"[VectorStore] Stored image → '{collection}' | id='{img_id}' | src='{source_uri}'"
        )
        return img_id

    async def search(
        self,
        query: str,
        collection: str = "research",
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        ## Description

        Embeds ``query`` with Ollama and runs an approximate nearest-neighbour
        search in the specified collection. Optionally filters results by
        metadata using a simple equality dict.

        ## Parameters

        - `query` (`str`)
          - Description: Natural language search query.
          - Example: ``"transformer multi-head attention"``

        - `collection` (`str`, optional)
          - Description: Collection to search.
          - Default: ``"research"``

        - `n_results` (`int`, optional)
          - Description: Maximum number of results.
          - Default: ``10``

        - `where` (`Optional[Dict[str, Any]]`, optional)
          - Description: Simple equality metadata filter.
          - Constraints: Values must be ``str | int | float | bool``.
          - Default: ``None`` (no filter)
          - Example: ``{"author": "Smith", "year": "2024"}``

        ## Returns

        `List[Dict[str, Any]]`

        Each entry:

        ```json
        {
            "id": "txt-a1b2-0",
            "document": "chunk text...",
            "metadata": {"source": "https://...", "type": "text", "author": "Smith"},
            "distance": 0.12
        }
        ```

        ## Side Effects

        - Makes HTTP call to Ollama.
        - Reads from ChromaDB.
        """
        emb = await _embed_text(query)
        if emb is None:
            _log.error("[VectorStore] search: query embedding failed.")
            return []

        return await self._query(collection, [emb], n_results, where)

    async def search_by_image(
        self,
        image_path: str,
        collection: str = "images",
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        ## Description

        Embeds ``image_path`` with SigLIP and performs an approximate
        nearest-neighbour search in the specified collection. Optionally
        filters results by metadata.

        ## Parameters

        - `image_path` (`str`)
          - Description: Path to the query image.
          - Constraints: File must exist.
          - Example: ``r"C:\\Users\\user\\Downloads\\query.png"``

        - `collection` (`str`, optional)
          - Description: Collection to search.
          - Default: ``"images"``

        - `n_results` (`int`, optional)
          - Description: Maximum number of results.
          - Default: ``10``

        - `where` (`Optional[Dict[str, Any]]`, optional)
          - Description: Simple equality metadata filter.
          - Constraints: Values must be ``str | int | float | bool``.
          - Default: ``None``
          - Example: ``{"scene": "outdoor"}``

        ## Returns

        `List[Dict[str, Any]]` — Same structure as ``search()``, with ``distance``
        representing cosine distance (lower = more similar).

        ## Side Effects

        - Loads SigLIP ONNX model on first call.
        - Reads from ChromaDB.
        """
        emb = await _embed_image(image_path)
        if emb is None:
            _log.error("[VectorStore] search_by_image: embedding failed.")
            return []

        return await self._query(collection, [emb], n_results, where)

    async def _query(
        self,
        collection: str,
        query_embeddings: List[List[float]],
        n_results: int,
        where: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        ## Description

        Internal helper — executes ChromaDB ``collection.query()`` in a thread
        and normalises raw output into a flat list of result dicts.

        ## Parameters

        - `collection` (`str`) — Target collection.
        - `query_embeddings` (`List[List[float]]`) — One query embedding.
        - `n_results` (`int`) — Result cap.
        - `where` (`Optional[Dict[str, Any]]`) — Simple equality filter dict.

        ## Returns

        `List[Dict[str, Any]]` — Flat normalised result list.
        """
        chroma_where = _build_where(where)

        def _run():
            col = self._get_collection(collection)
            total = col.count()
            if total == 0:
                return None
            safe_n = min(n_results, total)
            kwargs: Dict[str, Any] = {
                "query_embeddings": query_embeddings,
                "n_results": safe_n,
                "include": ["documents", "metadatas", "distances"],
            }
            if chroma_where:
                kwargs["where"] = chroma_where
            return col.query(**kwargs)

        raw = await asyncio.to_thread(_run)
        if not raw:
            return []

        return [
            {
                "id": rid,
                "document": doc,
                "metadata": meta,
                "distance": dist,
            }
            for rid, doc, meta, dist in zip(
                raw.get("ids", [[]])[0],
                raw.get("documents", [[]])[0],
                raw.get("metadatas", [[]])[0],
                raw.get("distances", [[]])[0],
            )
        ]

    async def get(
        self,
        collection: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        ## Description

        Retrieves records directly by ID or metadata filter — no query embedding
        required. Useful for existence checks and record inspection.

        ## Parameters

        - `collection` (`str`) — Target collection.

        - `ids` (`Optional[List[str]]`, optional)
          - Description: Explicit record IDs to fetch.
          - Example: ``["img-abc123", "txt-xyz-0"]``

        - `where` (`Optional[Dict[str, Any]]`, optional)
          - Description: Simple equality metadata filter.
          - Example: ``{"type": "image"}``

        ## Returns

        `List[Dict[str, Any]]` — Records without a distance field:

        ```json
        [{"id": "img-abc123", "document": "path/to/image.png", "metadata": {...}}]
        ```
        """
        chroma_where = _build_where(where)

        def _run():
            col = self._get_collection(collection)
            kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
            if ids:
                kwargs["ids"] = ids
            if chroma_where:
                kwargs["where"] = chroma_where
            return col.get(**kwargs)

        raw = await asyncio.to_thread(_run)

        return [
            {"id": rid, "document": doc, "metadata": meta}
            for rid, doc, meta in zip(
                raw.get("ids", []),
                raw.get("documents", []),
                raw.get("metadatas", []),
            )
        ]

    async def delete(
        self,
        collection: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        ## Description

        Deletes records from a collection by explicit IDs or metadata filter.
        At least one of ``ids`` or ``where`` must be provided.

        ## Parameters

        - `collection` (`str`) — Target collection.

        - `ids` (`Optional[List[str]]`, optional)
          - Description: Specific IDs to delete.

        - `where` (`Optional[Dict[str, Any]]`, optional)
          - Description: Simple equality filter — deletes all matching records.
          - Example: ``{"type": "image"}``

        ## Returns

        `int` — Approximate number of records deleted.

        ## Raises

        - `ValueError` — if neither ``ids`` nor ``where`` is provided.
        """
        if not ids and not where:
            raise ValueError("delete() requires at least one of: ids, where.")

        chroma_where = _build_where(where)

        def _run():
            col = self._get_collection(collection)
            before = col.count()
            kwargs: Dict[str, Any] = {}
            if ids:
                kwargs["ids"] = ids
            if chroma_where:
                kwargs["where"] = chroma_where
            col.delete(**kwargs)
            return before - col.count()

        removed = await asyncio.to_thread(_run)
        _log.info(f"[VectorStore] Deleted ~{removed} records from '{collection}'.")
        return removed

    async def count(self, collection: str) -> int:
        """
        ## Description

        Returns the total number of records in a collection.

        ## Parameters

        - `collection` (`str`) — Collection name.

        ## Returns

        `int` — Record count (0 if collection doesn't exist yet).
        """
        def _run():
            return self._get_collection(collection).count()

        return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------------
# Singleton — import this in your application code
# ---------------------------------------------------------------------------

vector_store = VectorStore()
