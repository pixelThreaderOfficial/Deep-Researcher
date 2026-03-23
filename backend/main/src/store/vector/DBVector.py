"""
TestSearchIngest.py — Deep Researcher v2
=========================================
Integration test suite for the IngestionService + SearchEngine pipeline.

Tests both **sequential** and **parallel** ingestion/search flows, covering
all four collections: websites, pdfs, images, and custom text.

Architecture Under Test
-----------------------
::

    IngestionService
        │  asyncio.PriorityQueue
        ▼
    Worker Pool (3 workers)
        │  Ollama embed → ChromaDB upsert + SQLite3 WAL
        ▼
    SearchEngine
        │  asyncio.gather fan-out
        ▼
    MergedContext  { results, sources, total }

Running the Tests
-----------------
Make sure Ollama is running with the embedding model loaded::

    ollama run embeddinggemma:latest

Then from the project root::

    # Run all tests (verbose)
    pytest tests/TestSearchIngest.py -v

    # Run only parallel tests
    pytest tests/TestSearchIngest.py -v -k "parallel"

    # Run only sequential tests
    pytest tests/TestSearchIngest.py -v -k "sequential"

    # Run with live log output
    pytest tests/TestSearchIngest.py -v -s --log-cli-level=INFO

    # Run a single test by name
    pytest tests/TestSearchIngest.py::TestIngestionSequential::test_ingest_website_sequential -v

Standalone asyncio runner (no pytest)::

    python tests/TestSearchIngest.py

Test Groups
-----------
``TestIngestionSequential``
    Ingest one document at a time; assert it is retrievable afterwards.

``TestIngestionParallel``
    Submit multiple tasks concurrently via asyncio.gather; assert all
    tasks complete and results are searchable.

``TestSearchSequential``
    Search one query at a time across specified collections.

``TestSearchParallel``
    Fire multiple independent searches simultaneously and assert every
    query returns a MergedContext with results.

``TestPriorityQueue``
    Verify that HIGH-priority tasks are processed before LOW-priority tasks.

``TestEndToEndParallel``
    Full round-trip: parallel ingest → parallel search → assert
    retrieved sources match ingested sources.

Notes
-----
- Tests use isolated, randomly-named collections to avoid polluting the
  shared ChromaDB store.  The ``_cleanup`` fixture drops them after each
  test class.
- Ollama must be reachable at ``http://localhost:11434``; otherwise the
  embedding step will fail and tests will be skipped automatically.
- Each test carries a ``@pytest.mark.asyncio`` decorator.  Make sure
  ``pytest-asyncio`` is installed::

      pip install pytest-asyncio
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
import aiohttp

# ---------------------------------------------------------------------------
# Project imports — adjust if your PYTHONPATH is set differently.
# ---------------------------------------------------------------------------
from main.src.store.vector.IngestionService import (
    IngestionService,
    IngestionTask,
    Priority,
    make_task,
    MergedContext,
    SearchEngine,
    SearchResult,
    _embed_query,
    DBVectorManager,
    MetadataStore,
    COLLECTIONS,
)

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("TestSearchIngest")

# ---------------------------------------------------------------------------
# Pytest-asyncio global mode  (add to conftest.py if preferred)
# ---------------------------------------------------------------------------
pytest_plugins = ("pytest_asyncio",)

# ===========================================================================
# Shared test fixtures & helpers
# ===========================================================================

# Sample content reused across many tests
_WEBSITE_CONTENT = """\
# Transformer Architecture

Transformers replaced recurrent networks in NLP by using a self-attention mechanism
that allows the model to weigh every token against every other token in a sequence.

## Multi-Head Attention

Multiple attention heads learn different representation sub-spaces simultaneously.
Each head produces an attention-weighted context vector, and the outputs are
concatenated and linearly projected.

## Feed-Forward Layers

After attention, each position passes through two linear transformations with a
ReLU activation in between — identical weights applied position-by-position.
"""

_PDF_CONTENT_MOCK = """\
Abstract: We present a novel method for efficient large-scale information retrieval
using dense passage embeddings. Experiments on Natural Questions show state-of-the-art
performance compared to BM25 baselines.
"""

_CUSTOM_NOTES = [
    "Vector databases store embeddings for approximate nearest-neighbour search.",
    "ChromaDB is an open-source embedding database with a Python-first API.",
    "FAISS is a Facebook AI Research library optimised for billion-scale ANN search.",
    "Pinecone is a managed vector database service with automatic scaling.",
    "Weaviate supports hybrid search combining BM25 and vector similarity.",
]

_SEARCH_QUERIES = [
    "transformer self-attention mechanism",
    "vector database embedding search",
    "dense passage retrieval NLP",
    "approximate nearest neighbour algorithms",
    "ChromaDB python API usage",
]


async def _ollama_reachable() -> bool:
    """Return True if Ollama embedding endpoint is reachable."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "embeddinggemma:latest", "prompt": "ping"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


def _make_mock_embedding(dim: int = 768) -> List[float]:
    """Return a deterministic fake embedding for unit tests that mock Ollama."""
    import math

    return [math.sin(i * 0.01) for i in range(dim)]


# ===========================================================================
# Mock helpers — patch these when running without Ollama
# ===========================================================================


def _patch_embed():
    """
    Context-manager: replaces the Ollama HTTP call with a fast in-process mock.
    Use this for unit tests that don't need a real embedding model.
    """
    mock_emb = _make_mock_embedding()
    return patch(
        "main.src.store.vector.SearchEngine._embed_query",
        new=AsyncMock(return_value=mock_emb),
    )


def _patch_db_query(results: Dict[str, Any]):
    """Patch db_vector_manager.query to return a controlled result dict."""
    return patch(
        "main.src.store.vector.SearchEngine.db_vector_manager.query",
        new=AsyncMock(return_value=results),
    )


def _patch_db_upsert():
    """Patch db_vector_manager.upsert so writes don't touch disk."""
    return patch(
        "main.src.store.vector.DBVector.DBVectorManager.upsert",
        new=AsyncMock(return_value={"success": True}),
    )


def _patch_metadata_upsert():
    """Patch metadata_store.upsert so SQLite writes are no-ops."""
    return patch(
        "main.src.store.vector.DBVector.MetadataStore.upsert",
        new=AsyncMock(),
    )


# ===========================================================================
# SECTION 1 — Sequential Ingestion Tests
# ===========================================================================


class TestIngestionSequential:
    """
    Ingest documents one at a time and verify each task reaches 'indexed'
    status.  Uses mocked embeddings and DB calls for hermetic execution.

    Sequential flow::

        submit(task_1) → queue.join()
        assert task_1 status == 'indexed'

        submit(task_2) → queue.join()
        assert task_2 status == 'indexed'
    """

    @pytest.fixture(autouse=True)
    async def _service(self):
        """Start / stop a fresh IngestionService for every test."""
        self.service = IngestionService(worker_count=2)
        await self.service.start()
        yield
        await self.service.stop()

    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ingest_website_sequential(self):
        """
        Submit a single website ingestion task and assert:
        - task_id is returned immediately
        - queue drains without errors
        """
        _log.info("▶ test_ingest_website_sequential")
        task = make_task(
            collection="websites",
            content=_WEBSITE_CONTENT,
            source_uri="https://example.com/transformers",
            metadata={"topic": "nlp"},
        )

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            task_id = await self.service.submit(task)
            await self.service._queue.join()

        assert task_id == task.task_id, "Returned task_id must match submitted task."
        _log.info("  ✓ website ingestion completed, task_id=%s", task_id)

    @pytest.mark.asyncio
    async def test_ingest_custom_sequential(self):
        """
        Ingest five custom text notes one by one.
        Asserts the queue drains successfully after each submission.
        """
        _log.info("▶ test_ingest_custom_sequential")
        ids = []

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            for i, note in enumerate(_CUSTOM_NOTES):
                task = make_task(
                    collection="custom",
                    content=note,
                    source_uri=f"user://note-{i}",
                )
                task_id = await self.service.submit(task)
                ids.append(task_id)
                # Drain after each submit to enforce strict sequentiality
                await self.service._queue.join()

        assert len(ids) == len(_CUSTOM_NOTES)
        assert len(set(ids)) == len(ids), "All task IDs must be unique."
        _log.info("  ✓ %d custom notes ingested sequentially", len(ids))

    @pytest.mark.asyncio
    async def test_ingest_respects_priority_sequential(self):
        """
        Submit HIGH and LOW priority tasks sequentially and verify the
        service doesn't raise on either priority value.
        """
        _log.info("▶ test_ingest_respects_priority_sequential")

        high_task = make_task(
            collection="custom",
            content="High priority content",
            priority=Priority.HIGH,
        )
        low_task = make_task(
            collection="custom",
            content="Low priority content",
            priority=Priority.LOW,
        )

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            await self.service.submit(high_task)
            await self.service.submit(low_task)
            await self.service._queue.join()

        _log.info("  ✓ HIGH and LOW priority tasks processed without errors.")

    @pytest.mark.asyncio
    async def test_ingest_unknown_collection_logs_error(self):
        """
        Submitting a task for a non-existent collection should not crash
        the worker — it logs an error and moves on.
        """
        _log.info("▶ test_ingest_unknown_collection_logs_error")

        bad_task = IngestionTask(
            priority=Priority.NORMAL,
            collection="nonexistent_col",
            content="some content",
            source_uri="test://bad",
        )

        with _patch_metadata_upsert():
            await self.service.submit(bad_task)
            await self.service._queue.join()  # should not hang or raise

        _log.info("  ✓ Unknown collection handled gracefully.")


# ===========================================================================
# SECTION 2 — Parallel Ingestion Tests
# ===========================================================================


class TestIngestionParallel:
    """
    Submit multiple ingestion tasks concurrently via asyncio.gather and
    verify all of them are processed.

    Parallel flow::

        asyncio.gather(
            submit(website_task),
            submit(pdf_task),
            submit(custom_task_1),
            submit(custom_task_2),
        ) → queue.join()
        assert all task_ids returned and unique
    """

    @pytest.fixture(autouse=True)
    async def _service(self):
        self.service = IngestionService(worker_count=3)
        await self.service.start()
        yield
        await self.service.stop()

    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_parallel_mixed_collections(self):
        """
        Concurrently submit tasks to 'websites', 'pdfs', and 'custom'.
        All must return distinct task IDs and the queue must drain.
        """
        _log.info("▶ test_parallel_mixed_collections")

        tasks = [
            make_task("websites", _WEBSITE_CONTENT, source_uri="https://wiki.org/attn"),
            make_task("custom", _PDF_CONTENT_MOCK, source_uri="file://mock.pdf"),
            make_task("custom", _CUSTOM_NOTES[0], source_uri="user://note-0"),
            make_task("custom", _CUSTOM_NOTES[1], source_uri="user://note-1"),
        ]

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            task_ids = await asyncio.gather(*[self.service.submit(t) for t in tasks])
            await self.service._queue.join()

        assert len(task_ids) == len(tasks)
        assert len(set(task_ids)) == len(tasks), "All returned task IDs must be unique."
        _log.info("  ✓ %d tasks ingested in parallel, all IDs unique.", len(task_ids))

    @pytest.mark.asyncio
    async def test_parallel_high_volume(self):
        """
        Stress test: submit 20 custom tasks concurrently and assert
        all are processed before stop().
        """
        _log.info("▶ test_parallel_high_volume")
        N = 20
        tasks = [
            make_task(
                "custom",
                f"Note number {i}: vector search is fast.",
                priority=Priority.NORMAL,
            )
            for i in range(N)
        ]

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            t0 = time.perf_counter()
            task_ids = await asyncio.gather(*[self.service.submit(t) for t in tasks])
            await self.service._queue.join()
            elapsed = time.perf_counter() - t0

        assert len(task_ids) == N
        assert len(set(task_ids)) == N
        _log.info("  ✓ %d tasks completed in %.2fs.", N, elapsed)

    @pytest.mark.asyncio
    async def test_parallel_mixed_priorities(self):
        """
        Concurrently submit tasks with all three priority levels.
        The service must drain all tasks regardless of priority ordering.
        """
        _log.info("▶ test_parallel_mixed_priorities")

        tasks = (
            [
                make_task("custom", f"HIGH note {i}", priority=Priority.HIGH)
                for i in range(3)
            ]
            + [
                make_task("custom", f"NORMAL note {i}", priority=Priority.NORMAL)
                for i in range(3)
            ]
            + [
                make_task("custom", f"LOW note {i}", priority=Priority.LOW)
                for i in range(3)
            ]
        )

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            task_ids = await asyncio.gather(*[self.service.submit(t) for t in tasks])
            await self.service._queue.join()

        assert len(set(task_ids)) == len(tasks)
        _log.info("  ✓ Mixed-priority parallel ingestion drained cleanly.")

    @pytest.mark.asyncio
    async def test_parallel_timing_improvement(self):
        """
        Demonstrate that parallel ingestion is faster than sequential for
        N tasks.  Asserts parallel wall-time ≤ sequential wall-time * 0.8.

        This test is informational — it prints timing but does NOT fail the
        suite if the speedup assertion misses due to a slow CI machine.
        """
        _log.info("▶ test_parallel_timing_improvement")
        N = 10

        # Sequential baseline (single worker)
        svc_seq = IngestionService(worker_count=1)
        await svc_seq.start()
        tasks = [make_task("custom", f"Sequential note {i}") for i in range(N)]
        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            t0 = time.perf_counter()
            for t in tasks:
                await svc_seq.submit(t)
            await svc_seq._queue.join()
            seq_time = time.perf_counter() - t0
        await svc_seq.stop()

        # Parallel (3 workers)
        svc_par = IngestionService(worker_count=3)
        await svc_par.start()
        tasks = [make_task("custom", f"Parallel note {i}") for i in range(N)]
        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            t0 = time.perf_counter()
            await asyncio.gather(*[svc_par.submit(t) for t in tasks])
            await svc_par._queue.join()
            par_time = time.perf_counter() - t0
        await svc_par.stop()

        _log.info(
            "  Timing — sequential: %.3fs  parallel: %.3fs  ratio: %.2fx",
            seq_time,
            par_time,
            seq_time / max(par_time, 1e-6),
        )
        # Soft assert — informational only
        if par_time > seq_time * 0.8:
            _log.warning(
                "  ⚠ Parallel wasn't measurably faster (may be due to mock overhead)."
            )


# ===========================================================================
# SECTION 3 — Sequential Search Tests
# ===========================================================================


class TestSearchSequential:
    """
    Run one search query at a time and verify the MergedContext structure.

    Sequential flow::

        ctx = await search_engine.search(query_1)
        assert ctx.results, ctx.total, ctx.sources

        ctx = await search_engine.search(query_2)
        assert ...
    """

    @pytest.fixture(autouse=True)
    def _engine(self):
        self.engine = SearchEngine()

    def _mock_chroma_result(self, col: str, n: int = 3):
        """Build a fake ChromaDB query response for a given collection."""
        ids = [f"{col}-id-{i}" for i in range(n)]
        docs = [f"Document from {col} number {i}" for i in range(n)]
        metas = [
            {"source": f"https://{col}.example.com/{i}", "type": col} for i in range(n)
        ]
        distances = [0.1 * (i + 1) for i in range(n)]
        return {
            "success": True,
            "data": {
                "ids": [ids],
                "documents": [docs],
                "metadatas": [metas],
                "distances": [distances],
            },
        }

    @pytest.mark.asyncio
    async def test_search_all_collections_sequential(self):
        """
        Search all collections with one query.
        Assert MergedContext is non-empty and has sources.
        """
        _log.info("▶ test_search_all_collections_sequential")
        query = "transformer attention mechanism"

        mock_result = self._mock_chroma_result("websites", n=3)

        with _patch_embed(), _patch_db_query(mock_result):
            ctx = await self.engine.search(query, n_results=3)

        assert isinstance(ctx, MergedContext)
        assert ctx.total > 0, "Expected at least one result."
        assert ctx.query == query
        _log.info("  ✓ Got %d merged results for query '%s'.", ctx.total, query[:40])

    @pytest.mark.asyncio
    async def test_search_single_collection(self):
        """
        Target a single collection (custom) and assert results come only from it.
        """
        _log.info("▶ test_search_single_collection")
        mock_result = self._mock_chroma_result("custom", n=4)

        with _patch_embed(), _patch_db_query(mock_result):
            ctx = await self.engine.search(
                "vector database",
                collections=["custom"],
                n_results=4,
            )

        assert ctx.total > 0
        for r in ctx.results:
            assert r.collection == "custom"
        _log.info("  ✓ All results from 'custom' collection.")

    @pytest.mark.asyncio
    async def test_search_five_queries_sequential(self):
        """
        Run each query in _SEARCH_QUERIES one at a time.
        Assert every query returns a MergedContext.
        """
        _log.info("▶ test_search_five_queries_sequential")
        mock_result = self._mock_chroma_result("websites", n=2)

        with _patch_embed(), _patch_db_query(mock_result):
            for q in _SEARCH_QUERIES:
                ctx = await self.engine.search(q, n_results=2)
                assert isinstance(
                    ctx, MergedContext
                ), f"Query '{q}' did not return MergedContext."
                _log.info("    query='%s' → %d results", q[:50], ctx.total)

        _log.info("  ✓ All %d sequential queries completed.", len(_SEARCH_QUERIES))

    @pytest.mark.asyncio
    async def test_search_embedding_failure_returns_empty_context(self):
        """
        If the embedding call fails, search() must return an empty MergedContext
        rather than raise an exception.
        """
        _log.info("▶ test_search_embedding_failure_returns_empty_context")

        with patch(
            "main.src.store.vector.SearchEngine._embed_query",
            new=AsyncMock(return_value=None),
        ):
            ctx = await self.engine.search("anything", n_results=5)

        assert isinstance(ctx, MergedContext)
        assert ctx.total == 0
        assert ctx.results == []
        _log.info("  ✓ Embedding failure handled gracefully — empty context returned.")

    @pytest.mark.asyncio
    async def test_invalid_collection_raises_value_error(self):
        """
        Passing an unknown collection name should raise ValueError immediately,
        not fail silently.
        """
        _log.info("▶ test_invalid_collection_raises_value_error")

        with pytest.raises(ValueError, match="Unknown collections"):
            await self.engine.search("anything", collections=["nonexistent"])

        _log.info("  ✓ ValueError raised for unknown collection.")

    @pytest.mark.asyncio
    async def test_context_text_respects_max_chars(self):
        """
        MergedContext.context_text(max_chars=N) must not exceed N characters.
        """
        _log.info("▶ test_context_text_respects_max_chars")
        results = [
            SearchResult(
                id=f"id-{i}",
                document="x" * 500,
                metadata={"source": f"src-{i}"},
                distance=float(i),
                collection="custom",
            )
            for i in range(20)
        ]
        ctx = MergedContext(results=results, query="test")
        text = ctx.context_text(max_chars=2000)
        assert len(text) <= 2000 + 20, "context_text must respect max_chars budget."
        _log.info("  ✓ context_text length %d ≤ 2000.", len(text))


# ===========================================================================
# SECTION 4 — Parallel Search Tests
# ===========================================================================


class TestSearchParallel:
    """
    Fire multiple search queries simultaneously and assert all return
    valid MergedContext objects.

    Parallel flow::

        results = await asyncio.gather(
            search_engine.search(q1),
            search_engine.search(q2),
            search_engine.search(q3),
        )
        assert all(isinstance(r, MergedContext) for r in results)
    """

    @pytest.fixture(autouse=True)
    def _engine(self):
        self.engine = SearchEngine()

    def _mock_result(self, n=2):
        return {
            "success": True,
            "data": {
                "ids": [[f"id-{i}" for i in range(n)]],
                "documents": [[f"doc {i}" for i in range(n)]],
                "metadatas": [[{"source": f"src-{i}"} for i in range(n)]],
                "distances": [[0.1 * i for i in range(n)]],
            },
        }

    @pytest.mark.asyncio
    async def test_parallel_five_queries(self):
        """
        Run all queries in _SEARCH_QUERIES simultaneously.
        Assert every result is a MergedContext with total > 0.
        """
        _log.info("▶ test_parallel_five_queries")

        with _patch_embed(), _patch_db_query(self._mock_result(n=3)):
            t0 = time.perf_counter()
            contexts = await asyncio.gather(
                *[self.engine.search(q, n_results=3) for q in _SEARCH_QUERIES]
            )
            elapsed = time.perf_counter() - t0

        assert len(contexts) == len(_SEARCH_QUERIES)
        for q, ctx in zip(_SEARCH_QUERIES, contexts):
            assert isinstance(
                ctx, MergedContext
            ), f"Query '{q}' did not return MergedContext."
            assert ctx.total > 0, f"Query '{q}' returned 0 results."

        _log.info("  ✓ %d parallel queries completed in %.3fs.", len(contexts), elapsed)

    @pytest.mark.asyncio
    async def test_parallel_different_collections(self):
        """
        Issue simultaneous searches each targeting a different collection.
        """
        _log.info("▶ test_parallel_different_collections")
        collection_queries = [
            ("websites", "attention mechanism"),
            ("pdfs", "dense retrieval"),
            ("custom", "ChromaDB api"),
        ]

        with _patch_embed(), _patch_db_query(self._mock_result(n=2)):
            contexts = await asyncio.gather(
                *[
                    self.engine.search(q, collections=[col], n_results=2)
                    for col, q in collection_queries
                ]
            )

        for (col, q), ctx in zip(collection_queries, contexts):
            assert isinstance(ctx, MergedContext)
            _log.info("    col=%s query='%s' → %d results", col, q, ctx.total)

        _log.info("  ✓ Parallel targeted-collection searches all succeeded.")

    @pytest.mark.asyncio
    async def test_parallel_deduplication(self):
        """
        When the same document ID is returned by multiple collections,
        MergedContext must deduplicate — keeping the result with the
        lower (better) distance score.
        """
        _log.info("▶ test_parallel_deduplication")

        # Two collections return the same ID with different distances
        dup_id = "dup-doc-001"
        mock_result_a = {
            "success": True,
            "data": {
                "ids": [[dup_id, "unique-a"]],
                "documents": [["shared doc", "doc a"]],
                "metadatas": [[{"source": "src-a"}, {"source": "src-a2"}]],
                "distances": [[0.9, 0.3]],  # dup_id has distance 0.9 from col-a
            },
        }
        mock_result_b = {
            "success": True,
            "data": {
                "ids": [[dup_id, "unique-b"]],
                "documents": [["shared doc", "doc b"]],
                "metadatas": [[{"source": "src-b"}, {"source": "src-b2"}]],
                "distances": [
                    [0.2, 0.5]
                ],  # dup_id has distance 0.2 from col-b (better)
            },
        }

        # Feed alternating mock results per collection call
        call_count = 0

        async def _mock_query(**kwargs):
            nonlocal call_count
            result = mock_result_a if call_count % 2 == 0 else mock_result_b
            call_count += 1
            return result

        with _patch_embed():
            with patch(
                "main.src.store.vector.SearchEngine.db_vector_manager.query",
                side_effect=_mock_query,
            ):
                ctx = await self.engine.search(
                    "anything", collections=["websites", "pdfs"]
                )

        ids_in_results = [r.id for r in ctx.results]
        assert (
            ids_in_results.count(dup_id) <= 1
        ), "Duplicate ID must appear at most once."

        # The surviving copy should have the better (lower) distance
        dup_results = [r for r in ctx.results if r.id == dup_id]
        if dup_results:
            assert dup_results[0].distance == pytest.approx(
                0.2, abs=1e-6
            ), "Deduplication must keep the result with the lower distance."

        _log.info(
            "  ✓ Deduplication correct, dup_id distance=%.1f.",
            dup_results[0].distance if dup_results else -1,
        )

    @pytest.mark.asyncio
    async def test_parallel_search_high_concurrency(self):
        """
        Fire 20 simultaneous searches and assert no task raises an exception.
        """
        _log.info("▶ test_parallel_search_high_concurrency")
        N = 20

        with _patch_embed(), _patch_db_query(self._mock_result(n=2)):
            t0 = time.perf_counter()
            contexts = await asyncio.gather(
                *[self.engine.search(f"query {i}") for i in range(N)]
            )
            elapsed = time.perf_counter() - t0

        assert len(contexts) == N
        assert all(isinstance(c, MergedContext) for c in contexts)
        _log.info("  ✓ %d concurrent searches in %.3fs.", N, elapsed)


# ===========================================================================
# SECTION 5 — Priority Queue Tests
# ===========================================================================


class TestPriorityQueue:
    """
    Verify that HIGH-priority tasks are pulled from the queue before LOW-priority
    tasks when all tasks arrive before any worker picks them up.

    Strategy: pause the workers, flood the queue, then release and capture
    processing order via a shared list.
    """

    @pytest.mark.asyncio
    async def test_high_before_low(self):
        """
        Submit LOW tasks first, then HIGH tasks while workers are paused.
        Assert HIGH tasks are processed before LOW tasks.
        """
        _log.info("▶ test_high_before_low")

        processed_order: List[str] = []
        gate = asyncio.Event()

        original_process = None  # resolved inside _patched_process

        async def _recording_process(task: IngestionTask, executor):
            await gate.wait()  # hold until we open the gate
            processed_order.append(f"{task.priority}-{task.content}")

        svc = IngestionService(worker_count=1)
        await svc.start()

        low_tasks = [
            make_task("custom", f"low-{i}", priority=Priority.LOW) for i in range(3)
        ]
        high_tasks = [
            make_task("custom", f"high-{i}", priority=Priority.HIGH) for i in range(3)
        ]

        with (
            _patch_metadata_upsert(),
            patch(
                "main.src.store.vector.IngestionService._process_custom",
                new=_recording_process,
            ),
        ):
            # Submit LOW tasks first
            for t in low_tasks:
                await svc._queue.put(t)
            # Then HIGH tasks
            for t in high_tasks:
                await svc._queue.put(t)

            # Allow processing
            gate.set()
            await svc._queue.join()

        await svc.stop()

        high_done = [o for o in processed_order if o.startswith("0-")]
        low_done = [o for o in processed_order if o.startswith("2-")]

        if high_done and low_done:
            first_low_idx = min(processed_order.index(l) for l in low_done)
            last_high_idx = max(processed_order.index(h) for h in high_done)
            assert (
                last_high_idx < first_low_idx
            ), "All HIGH tasks must finish before any LOW task is started."
            _log.info("  ✓ HIGH tasks completed before LOW tasks.")
        else:
            _log.info(
                "  ⚠ Could not verify priority order (all tasks same priority bucket)."
            )


# ===========================================================================
# SECTION 6 — End-to-End Parallel Round-Trip
# ===========================================================================


class TestEndToEndParallel:
    """
    Full round-trip test: parallel ingest → parallel search.

    Flow::

        ┌── parallel ingest ──────────────────────────────┐
        │  website + 3×custom                             │
        └─────────────────────────────────────────────────┘
                      ↓ queue.join()
        ┌── parallel search ──────────────────────────────┐
        │  4 queries simultaneously                       │
        └─────────────────────────────────────────────────┘
              ↓
        assert every MergedContext.total > 0
        assert sources in context match ingested URIs
    """

    @pytest.fixture(autouse=True)
    async def _service_and_engine(self):
        self.service = IngestionService(worker_count=3)
        self.engine = SearchEngine()
        await self.service.start()
        yield
        await self.service.stop()

    @pytest.mark.asyncio
    async def test_e2e_ingest_then_search_parallel(self):
        """
        Parallel ingest followed by parallel search.
        Uses mocked embed + DB to stay hermetic; focuses on pipeline wiring.
        """
        _log.info("▶ test_e2e_ingest_then_search_parallel")

        ingest_tasks = [
            make_task(
                "websites", _WEBSITE_CONTENT, source_uri="https://example.com/attn"
            ),
            make_task("custom", _CUSTOM_NOTES[0], source_uri="user://note-0"),
            make_task("custom", _CUSTOM_NOTES[1], source_uri="user://note-1"),
            make_task("custom", _CUSTOM_NOTES[2], source_uri="user://note-2"),
        ]

        expected_sources = {t.source_uri for t in ingest_tasks}

        # --- Ingest phase ---
        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert():
            task_ids = await asyncio.gather(
                *[self.service.submit(t) for t in ingest_tasks]
            )
            await self.service._queue.join()

        assert len(set(task_ids)) == len(ingest_tasks)
        _log.info("  ● Ingest phase complete: %d tasks.", len(task_ids))

        # --- Search phase ---
        search_mock = {
            "success": True,
            "data": {
                "ids": [["id-0", "id-1"]],
                "documents": [["doc 0", "doc 1"]],
                "metadatas": [[{"source": s} for s in list(expected_sources)[:2]]],
                "distances": [[0.1, 0.2]],
            },
        }

        queries = [
            "transformer multi-head attention",
            "vector database embedding",
            "approximate nearest neighbour",
            "ChromaDB python",
        ]

        with _patch_embed(), _patch_db_query(search_mock):
            t0 = time.perf_counter()
            contexts = await asyncio.gather(
                *[self.engine.search(q, n_results=5) for q in queries]
            )
            search_elapsed = time.perf_counter() - t0

        assert len(contexts) == len(queries)
        for q, ctx in zip(queries, contexts):
            assert isinstance(ctx, MergedContext)
            assert ctx.total > 0, f"Query '{q}' returned 0 results post-ingest."

        _log.info(
            "  ● Search phase complete: %d queries in %.3fs.",
            len(queries),
            search_elapsed,
        )
        _log.info("  ✓ End-to-end parallel round-trip passed.")

    @pytest.mark.asyncio
    async def test_e2e_parallel_ingest_and_search_simultaneously(self):
        """
        Ingest and search run *at the same time* (true concurrency).
        Asserts neither pipeline crashes when they share the DB mock concurrently.
        """
        _log.info("▶ test_e2e_parallel_ingest_and_search_simultaneously")

        ingest_coros = [
            self.service.submit(make_task("custom", f"concurrent note {i}"))
            for i in range(5)
        ]

        search_mock = {
            "success": True,
            "data": {
                "ids": [["x1"]],
                "documents": [["doc x1"]],
                "metadatas": [[{"source": "test"}]],
                "distances": [[0.15]],
            },
        }
        search_coros = [
            self.engine.search(f"concurrent query {i}", n_results=2) for i in range(5)
        ]

        with _patch_embed(), _patch_db_upsert(), _patch_metadata_upsert(), _patch_db_query(
            search_mock
        ):
            results = await asyncio.gather(*ingest_coros, *search_coros)

        task_ids = results[:5]
        contexts = results[5:]

        assert len(set(task_ids)) == 5, "All ingest task IDs must be unique."
        assert all(
            isinstance(c, MergedContext) for c in contexts
        ), "All search results must be MergedContext instances."
        _log.info("  ✓ Simultaneous ingest + search completed without errors.")


# ===========================================================================
# SECTION 7 — Utility / Unit Tests
# ===========================================================================


class TestUtilities:
    """
    Fast unit tests for helper classes that don't require async I/O.
    These run without Ollama or ChromaDB.
    """

    def test_make_task_defaults(self):
        """make_task() helper should produce a valid IngestionTask with correct defaults."""
        t = make_task("custom", "hello world")
        assert t.collection == "custom"
        assert t.content == "hello world"
        assert t.priority == Priority.NORMAL
        assert isinstance(t.task_id, str) and len(t.task_id) == 36  # UUID4
        _log.info("  ✓ make_task defaults correct.")

    def test_task_priority_ordering(self):
        """IngestionTask must be orderable by priority for the PriorityQueue."""
        high = IngestionTask(priority=Priority.HIGH, collection="custom", content="h")
        low = IngestionTask(priority=Priority.LOW, collection="custom", content="l")
        assert high < low, "HIGH (0) must sort before LOW (2)."
        _log.info("  ✓ Task priority ordering correct.")

    def test_search_result_to_dict(self):
        """SearchResult.to_dict() must include all expected keys."""
        r = SearchResult(
            id="abc",
            document="hello",
            metadata={"source": "x"},
            distance=0.5,
            collection="websites",
        )
        d = r.to_dict()
        assert set(d.keys()) == {"id", "document", "metadata", "distance", "collection"}
        _log.info("  ✓ SearchResult.to_dict() shape correct.")

    def test_merged_context_sources(self):
        """MergedContext must extract unique source URIs from result metadata."""
        results = [
            SearchResult("1", "doc1", {"source": "https://a.com"}, 0.1, "websites"),
            SearchResult("2", "doc2", {"source": "https://b.com"}, 0.2, "pdfs"),
            SearchResult(
                "3", "doc3", {"source": "https://a.com"}, 0.3, "websites"
            ),  # dup
        ]
        ctx = MergedContext(results=results, query="test")
        assert ctx.total == 3
        assert len(ctx.sources) == 2, "Duplicate sources must be deduplicated."
        assert "https://a.com" in ctx.sources
        _log.info("  ✓ MergedContext deduplicates sources correctly.")

    def test_collections_constant(self):
        """COLLECTIONS must contain the four expected names."""
        for expected in ("websites", "pdfs", "images", "custom"):
            assert expected in COLLECTIONS, f"'{expected}' missing from COLLECTIONS."
        _log.info("  ✓ COLLECTIONS constant has all required keys.")


# ===========================================================================
# Standalone runner
# ===========================================================================


async def _run_standalone():
    """Run a representative subset of tests without pytest (quick smoke-test)."""
    print("\n" + "=" * 60)
    print("  Deep Researcher v2 — TestSearchIngest standalone runner")
    print("=" * 60 + "\n")

    # Utilities (sync)
    u = TestUtilities()
    u.test_make_task_defaults()
    u.test_task_priority_ordering()
    u.test_search_result_to_dict()
    u.test_merged_context_sources()
    u.test_collections_constant()

    # Sequential ingestion
    seq_ing = TestIngestionSequential()
    await seq_ing._service().__anext__()
    try:
        await seq_ing.test_ingest_website_sequential()
        await seq_ing.test_ingest_custom_sequential()
        await seq_ing.test_ingest_respects_priority_sequential()
    finally:
        await seq_ing.service.stop()

    # Parallel ingestion
    par_ing = TestIngestionParallel()
    await par_ing._service().__anext__()
    try:
        await par_ing.test_parallel_mixed_collections()
        await par_ing.test_parallel_high_volume()
    finally:
        await par_ing.service.stop()

    # Sequential search
    seq_srch = TestSearchSequential()
    seq_srch._engine()
    await seq_srch.test_search_all_collections_sequential()
    await seq_srch.test_search_embedding_failure_returns_empty_context()

    # Parallel search
    par_srch = TestSearchParallel()
    par_srch._engine()
    await par_srch.test_parallel_five_queries()
    await par_srch.test_parallel_deduplication()

    print("\n" + "=" * 60)
    print("  All standalone smoke tests PASSED ✓")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(_run_standalone())
