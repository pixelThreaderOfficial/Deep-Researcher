from chromadb import Client as ChromaClient
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from typing import List, Dict, Any, Optional, Union
import dotenv, os
import uuid
import hashlib

dotenv.load_dotenv()

collectionName = "deep_researcher"

if os.getenv("APPLICATION_PHASE") == "development":
    collectionName="deep_researcher_beta"

vectorClient = ChromaClient()

# Main research collection for RAG
research_collection = vectorClient.get_or_create_collection(name=collectionName)

# Embedding function
google_ef = GoogleGenerativeAiEmbeddingFunction(api_key=os.getenv("GEMINI_API_KEY"))


# ========================================
# UTILITY FUNCTIONS
# ========================================

def generate_document_id(content: str) -> str:
    """Generate a unique ID for a document based on its content hash"""
    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    return f"doc_{content_hash}"

def generate_ids_for_documents(documents: List[str]) -> List[str]:
    """Generate unique IDs for a list of documents"""
    return [generate_document_id(doc) for doc in documents]

def embed_documents(documents: List[str]) -> List[List[float]]:
    """Embed a list of documents using Google Generative AI"""
    return google_ef(documents)


# ========================================
# CRUD OPERATIONS
# ========================================

def create_documents(documents: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    CREATE: Add documents to the collection

    Args:
        documents: List of document strings
        metadatas: Optional list of metadata dictionaries for each document
        ids: Optional list of custom IDs for documents

    Returns:
        Dict with success status and created document info
    """
    try:
        if not documents:
            return {"success": False, "error": "No documents provided"}

        # Generate IDs if not provided
        if ids is None:
            ids = generate_ids_for_documents(documents)

        # Ensure we have embeddings
        embeddings = embed_documents(documents)

        # Prepare metadatas
        if metadatas is None:
            metadatas = [{"created_at": str(os.times()[-1])} for _ in documents]
        else:
            # Ensure all documents have metadata
            while len(metadatas) < len(documents):
                metadatas.append({"created_at": str(os.times()[-1])})

        # Add to collection
        research_collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        return {
            "success": True,
            "message": f"Successfully added {len(documents)} documents",
            "document_ids": ids,
            "count": len(documents)
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to create documents: {str(e)}"}


def read_document(document_id: str) -> Dict[str, Any]:
    """
    READ: Get a specific document by ID

    Args:
        document_id: The ID of the document to retrieve

    Returns:
        Dict with document data or error
    """
    try:
        result = research_collection.get(ids=[document_id], include=["documents", "metadatas"])

        if not result["documents"]:
            return {"success": False, "error": f"Document with ID '{document_id}' not found"}

        return {
            "success": True,
            "document_id": document_id,
            "content": result["documents"][0],
            "metadata": result["metadatas"][0] if result["metadatas"] else {}
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to read document: {str(e)}"}


def read_all_documents(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    READ ALL: Get all documents in the collection

    Args:
        limit: Maximum number of documents to return
        offset: Number of documents to skip

    Returns:
        Dict with list of documents
    """
    try:
        result = research_collection.get(
            include=["documents", "metadatas"],
            limit=limit,
            offset=offset
        )

        documents = []
        for i, doc in enumerate(result["documents"]):
            documents.append({
                "id": result["ids"][i],
                "content": doc,
                "metadata": result["metadatas"][i] if result["metadatas"] else {}
            })

        return {
            "success": True,
            "documents": documents,
            "count": len(documents),
            "total": research_collection.count()
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to read documents: {str(e)}"}


def update_document(document_id: str, new_content: Optional[str] = None, new_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    UPDATE: Update an existing document

    Args:
        document_id: ID of the document to update
        new_content: New content for the document (optional)
        new_metadata: New metadata for the document (optional)

    Returns:
        Dict with success status
    """
    try:
        # Check if document exists
        existing = research_collection.get(ids=[document_id])
        if not existing["documents"]:
            return {"success": False, "error": f"Document with ID '{document_id}' not found"}

        update_data = {}

        if new_content is not None:
            # Re-embed the new content
            embeddings = embed_documents([new_content])
            update_data["documents"] = [new_content]
            update_data["embeddings"] = embeddings

        if new_metadata is not None:
            update_data["metadatas"] = [new_metadata]

        if update_data:
            research_collection.update(ids=[document_id], **update_data)

        return {
            "success": True,
            "message": f"Successfully updated document '{document_id}'",
            "document_id": document_id
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to update document: {str(e)}"}


def delete_document(document_id: str) -> Dict[str, Any]:
    """
    DELETE: Remove a document from the collection

    Args:
        document_id: ID of the document to delete

    Returns:
        Dict with success status
    """
    try:
        # Check if document exists
        existing = research_collection.get(ids=[document_id])
        if not existing["documents"]:
            return {"success": False, "error": f"Document with ID '{document_id}' not found"}

        research_collection.delete(ids=[document_id])

        return {
            "success": True,
            "message": f"Successfully deleted document '{document_id}'",
            "document_id": document_id
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to delete document: {str(e)}"}


def delete_all_documents() -> Dict[str, Any]:
    """
    DELETE ALL: Remove all documents from the collection

    Returns:
        Dict with success status
    """
    try:
        count = research_collection.count()
        research_collection.delete(where={})  # Delete all documents

        return {
            "success": True,
            "message": f"Successfully deleted all {count} documents",
            "deleted_count": count
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to delete all documents: {str(e)}"}


# ========================================
# QUERY OPERATIONS
# ========================================

def query_documents(query: str, max_results: int = 10, include_metadata: bool = True) -> Dict[str, Any]:
    """
    Query documents by semantic similarity

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        include_metadata: Whether to include metadata in results

    Returns:
        Dict with query results
    """
    try:
        include = ["documents", "distances"]
        if include_metadata:
            include.append("metadatas")

        result = research_collection.query(
            query_texts=[query],
            n_results=max_results,
            include=include
        )

        results = []
        for i, doc in enumerate(result["documents"][0]):
            result_item = {
                "id": result["ids"][0][i],
                "content": doc,
                "distance": result["distances"][0][i]
            }
            if include_metadata and result["metadatas"]:
                result_item["metadata"] = result["metadatas"][0][i]
            results.append(result_item)

        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results)
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to query documents: {str(e)}"}


def get_collection_stats() -> Dict[str, Any]:
    """
    Get statistics about the collection

    Returns:
        Dict with collection statistics
    """
    try:
        count = research_collection.count()
        return {
            "success": True,
            "collection_name": collectionName,
            "document_count": count,
            "status": "active"
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to get collection stats: {str(e)}"}


# ========================================
# BACKWARD COMPATIBILITY
# ========================================

def add_documents(documents: List[str]) -> Dict[str, Any]:
    """Backward compatibility function"""
    return create_documents(documents)