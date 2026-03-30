"""
test_vector.py — Deep Researcher v2
=====================================
Real-world integration demo for VectorStore.

Covers:
  1. Store text chunks from a .md file  → collection "research"
  2. Store text with metadata            → collection "web-scrapes"
  3. Store three images with metadata    → collection "images"
  4. Search text with metadata filter    → collection "research"
  5. Search text without filter          → collection "web-scrapes"
  6. Search by image (known sample)      → collection "images"
  7. Search by image (unknown image)     → collection "images"
  8. Get record by ID                    → collection "images"
  9. Count records in each collection
 10. Show end-usage API reference

Run from backend/:
    uv run python tests/test_vector.py
"""

import asyncio
import logging

logging.basicConfig(
    level=logging.WARNING,          # suppress library noise
    format="%(levelname)s | %(name)s | %(message)s"
)

# ── sample paths ─────────────────────────────────────────────────────────────
TEXT_FILE     = r"D:\Commercial\pixelThreader\pixelThreader OpenSource\Deep Researcher v2\backend\tests\test_research_prompts.md"

IMAGES = [
    r"c:\Users\ranaw\Downloads\carbon (1).png",
    r"c:\Users\ranaw\Downloads\carbon (3).png",
    r"c:\Users\ranaw\Downloads\localhost_4173_chat.png",
]

SEARCH_IMAGE  = IMAGES[0]                                       # known: carbon (1).png
UNKNOWN_IMAGE = r"c:\Users\ranaw\Downloads\G5GXnEUXcAAkADU.jpg" # unknown image


# ── helpers ───────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def show_results(results, label: str) -> None:
    print(f"\n  [{label}] → {len(results)} result(s)")
    for i, r in enumerate(results, 1):
        snippet = r["document"][:80].replace("\n", " ")
        meta    = r["metadata"]
        dist    = r.get("distance", "n/a")
        print(f"    {i}. dist={dist:.4f}" if isinstance(dist, float) else f"    {i}.", end="  ")
        print(f'id="{r["id"]}"')
        print(f"       snippet: {snippet!r}")
        print(f"       meta:    {meta}")


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    from main.src.store.vector import vector_store

    print("\n" + "=" * 60)
    print("  VectorStore — Real-World Integration Test")
    print("=" * 60)

    # ── 1. Store text from .md file ──────────────────────────────────────────
    section("1 / Store text from .md file → 'research'")

    with open(TEXT_FILE, encoding="utf-8") as f:
        text = f.read()

    print(f"  File: {TEXT_FILE}")
    print(f"  Characters: {len(text)}")

    stored_text_ids = await vector_store.add_text(
        text=text,
        collection="research",
        source_uri=TEXT_FILE,
        metadata={
            "topic":  "research-prompts",
            "format": "markdown",
            "author": "DeepResearcher",
        },
    )
    print(f"  Stored {len(stored_text_ids)} chunk(s).")
    if stored_text_ids:
        print(f"  First ID: {stored_text_ids[0]}")

    # ── 2. Store additional text with different metadata ──────────────────────
    section("2 / Store web-scraped text → 'web-scrapes'")

    web_text = """
    ChromaDB is an open-source embedding database that makes it easy to build
    LLM apps by making knowledge, facts, and skills pluggable for LLMs.
    It stores embeddings and their metadata, embeds documents and queries,
    and searches the embeddings. ChromaDB supports similarity search using
    cosine distance and Euclidean distance metrics.
    """

    web_ids = await vector_store.add_text(
        text=web_text,
        collection="web-scrapes",
        source_uri="https://docs.trychroma.com/",
        metadata={
            "site":     "trychroma.com",
            "category": "documentation",
        },
    )
    print(f"  Stored {len(web_ids)} chunk(s) → 'web-scrapes'.")

    # ── 3. Store images ───────────────────────────────────────────────────────
    section("3 / Store 3 images → 'images'")

    image_metas = [
        {"scene": "code-screenshot", "tool": "carbon",     "format": "png"},
        {"scene": "code-screenshot", "tool": "carbon",     "format": "png"},
        {"scene": "ui-screenshot",   "tool": "localhost",  "format": "png"},
    ]

    stored_image_ids = []
    for img_path, meta in zip(IMAGES, image_metas):
        img_id = await vector_store.add_image(
            image_path=img_path,
            collection="images",
            source_uri=img_path,
            metadata=meta,
        )
        if img_id:
            stored_image_ids.append(img_id)
            print(f"  ✓ Stored: {img_path.split('\\')[-1]}  →  id={img_id!r}")
        else:
            print(f"  ✗ FAILED: {img_path}")

    # ── 4. Search text with metadata filter ───────────────────────────────────
    section("4 / Search 'research' with metadata filter")

    results = await vector_store.search(
        query="research methodology and prompts",
        collection="research",
        n_results=3,
        where={"author": "DeepResearcher"},  # only our stored docs
    )
    show_results(results, "research | where author=DeepResearcher")

    # ── 5. Search text without filter ─────────────────────────────────────────
    section("5 / Search 'web-scrapes' without filter")

    results = await vector_store.search(
        query="embedding database similarity search",
        collection="web-scrapes",
        n_results=5,
    )
    show_results(results, "web-scrapes")

    # ── 6. Search by known image ──────────────────────────────────────────────
    section("6 / Search by image (known: carbon (1).png)")

    results = await vector_store.search_by_image(
        image_path=SEARCH_IMAGE,
        collection="images",
        n_results=3,
    )
    show_results(results, "images | query=carbon (1).png")

    # ── 7. Search by known image with metadata filter ─────────────────────────
    section("7 / Search by image with metadata filter (scene=code-screenshot)")

    results = await vector_store.search_by_image(
        image_path=SEARCH_IMAGE,
        collection="images",
        n_results=5,
        where={"scene": "code-screenshot"},
    )
    show_results(results, "images | scene=code-screenshot")

    # ── 8. Search by unknown image ────────────────────────────────────────────
    section("8 / Search by UNKNOWN image → what does it find?")

    results = await vector_store.search_by_image(
        image_path=UNKNOWN_IMAGE,
        collection="images",
        n_results=3,
    )
    show_results(results, "images | query=G5GXnEUX.jpg (unknown)")

    # ── 9. Get a record by ID ─────────────────────────────────────────────────
    section("9 / Get image record by ID")

    if stored_image_ids:
        records = await vector_store.get(
            collection="images",
            ids=[stored_image_ids[0]],
        )
        print(f"  Record: {records}")

    # ── 10. Get with metadata filter ──────────────────────────────────────────
    section("10 / Get all 'code-screenshot' images by metadata filter")

    records = await vector_store.get(
        collection="images",
        where={"scene": "code-screenshot"},
    )
    for r in records:
        print(f"  id={r['id']}  source={r['metadata'].get('source','?')}")

    # ── 11. Count records ─────────────────────────────────────────────────────
    section("11 / Count records in all collections")

    for col in ["research", "web-scrapes", "images"]:
        n = await vector_store.count(col)
        print(f"  {col:12s} → {n} record(s)")

    # ── 12. End-usage API reference ───────────────────────────────────────────
    section("12 / END-USAGE REFERENCE (how to use in your system)")

    print("""
  from main.src.store.vector import vector_store

  # ─ TEXT ────────────────────────────────────────────────────────
  ids = await vector_store.add_text(
      text="...",
      collection="research",          # or "web-scrapes" or any custom name
      source_uri="https://...",
      metadata={"author": "X", "year": "2024"},
  )

  results = await vector_store.search(
      query="your search query",
      collection="research",
      n_results=10,
      where={"author": "X", "year": "2024"},  # optional — omit to search all
  )
  # results → list of dicts: [{id, document, metadata, distance}, ...]

  # ─ IMAGE ───────────────────────────────────────────────────────
  img_id = await vector_store.add_image(
      image_path=r"C:\\path\\to\\image.png",
      collection="images",
      source_uri=r"C:\\path\\to\\image.png",
      metadata={"scene": "outdoor", "camera": "iPhone"},
  )

  results = await vector_store.search_by_image(
      image_path=r"C:\\path\\to\\query.png",
      collection="images",
      n_results=5,
      where={"scene": "outdoor"},             # optional metadata filter
  )
  # results → [{id, document, metadata, distance}, ...]

  # ─ CRUD ────────────────────────────────────────────────────────
  records = await vector_store.get("images", ids=["img-abc123"])
  records = await vector_store.get("images", where={"scene": "outdoor"})

  deleted = await vector_store.delete("images", ids=["img-abc123"])
  deleted = await vector_store.delete("images", where={"scene": "outdoor"})

  count   = await vector_store.count("images")
""")

    print("=" * 60)
    print("  ✓  All steps completed.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
