"""
main.src.store.vector
======================
Vector DB package — exposes the single ``vector_store`` singleton
and the ``COLLECTIONS`` constant listing default collection names.

Usage::

    from main.src.store.vector import vector_store, COLLECTIONS
"""

from main.src.store.vector.VectorStore import vector_store, COLLECTIONS

__all__ = ["vector_store", "COLLECTIONS"]
