from chromadb import Client as ChromaClient, Settings
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from typing import List, Dict, Any, Optional, Union
import dotenv, os, hashlib
from pathlib import Path

dotenv.load_dotenv()

collectionName = "deep_researcher"

if os.getenv("APPLICATION_PHASE") == "development":
    collectionName="deep_researcher_beta"

# Set up ChromaDB persistence directory inside rag_store/
RAG_DB_PATH = Path(__file__).parent / "rag_vector_db"
RAG_DB_PATH.mkdir(exist_ok=True)

# Initialize ChromaDB client with persistent storage
# Using the latest ChromaDB best practices
try:
    vectorClient = ChromaClient(Settings(
        is_persistent=True,
        persist_directory=str(RAG_DB_PATH),
        anonymized_telemetry=False
    ))
except Exception as e:
    # Fallback for older ChromaDB versions
    print(f"Warning: Could not initialize ChromaDB with Settings: {e}")
    print("Falling back to basic client initialization...")
    vectorClient = ChromaClient(path=str(RAG_DB_PATH))

# Main research collection for RAG with embedding function
google_ef = GoogleGenerativeAiEmbeddingFunction(api_key=os.getenv("GEMINI_API_KEY"))

research_collection = vectorClient.get_or_create_collection(
    name=collectionName,
    embedding_function=google_ef,
    metadata={"description": "Deep research knowledge base"}
)


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
    # Since embedding function is set at collection level, this is now redundant
    # but kept for backward compatibility
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

        # Prepare metadatas
        if metadatas is None:
            metadatas = [{"created_at": str(os.times()[-1])} for _ in documents]
        else:
            # Ensure all documents have metadata
            while len(metadatas) < len(documents):
                metadatas.append({"created_at": str(os.times()[-1])})

        # Add to collection (embeddings are handled automatically by the collection's embedding function)
        research_collection.add(
            documents=documents,
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
            # Collection will automatically re-embed the new content
            update_data["documents"] = [new_content]

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

def query_documents(query: str, max_results: int = 10, include_metadata: bool = True, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Query documents by semantic similarity

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        include_metadata: Whether to include metadata in results
        where: Optional metadata filters (e.g., {"source_type": "web_scrape"})

    Returns:
        Dict with query results
    """
    try:
        include = ["documents", "distances"]
        if include_metadata:
            include.append("metadatas")

        # Ensure we don't exceed available documents
        total_docs = research_collection.count()
        n_results = min(max_results, total_docs) if total_docs > 0 else max_results

        result = research_collection.query(
            query_texts=[query],
            n_results=n_results,
            include=include,
            where=where
        )

        results = []
        if result["documents"] and len(result["documents"]) > 0:
            for i, doc in enumerate(result["documents"][0]):
                result_item = {
                    "id": result["ids"][0][i],
                    "content": doc,
                    "distance": result["distances"][0][i]
                }
                if include_metadata and result["metadatas"] and len(result["metadatas"]) > 0:
                    result_item["metadata"] = result["metadatas"][0][i]
                results.append(result_item)

        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "total_available": total_docs
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
        metadata = research_collection.metadata or {}

        return {
            "success": True,
            "collection_name": collectionName,
            "document_count": count,
            "status": "active",
            "metadata": metadata,
            "embedding_function": "GoogleGenerativeAiEmbeddingFunction"
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to get collection stats: {str(e)}"}


def list_collections() -> Dict[str, Any]:
    """
    List all collections in the database

    Returns:
        Dict with list of collections
    """
    try:
        collections = vectorClient.list_collections()
        collection_info = []

        for collection in collections:
            info = {
                "name": collection.name,
                "id": getattr(collection, 'id', None),
                "document_count": collection.count(),
                "metadata": collection.metadata or {}
            }
            collection_info.append(info)

        return {
            "success": True,
            "collections": collection_info,
            "count": len(collection_info)
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to list collections: {str(e)}"}


def reset_collection() -> Dict[str, Any]:
    """
    Reset the research collection (delete all documents)

    Returns:
        Dict with reset status
    """
    try:
        count_before = research_collection.count()
        research_collection.delete(where={})  # Delete all documents

        return {
            "success": True,
            "message": f"Successfully reset collection. Deleted {count_before} documents.",
            "documents_deleted": count_before
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to reset collection: {str(e)}"}


# ========================================
# SCRAPED CONTENT HELPER
# ========================================

def save_scraped_content(scraped_content: Dict[str, str]) -> Dict[str, Any]:
    """
    Save scraped content to RAG store.
    
    This function takes scraped content (URL -> formatted content string),
    splits it into chunks, and saves it to the RAG store with metadata.
    
    Args:
        scraped_content: Dictionary mapping URL to formatted content string
        
    Returns:
        Dict with success status and document IDs
        
    Example:
        >>> scraped = {
        ...     "https://example.com": "Article content here...",
        ...     "https://example2.com": "More content here..."
        ... }
        >>> result = save_scraped_content(scraped)
        >>> print(result["success"])
        True
    """
    from datetime import datetime
    
    try:
        if not scraped_content:
            return {
                "success": False,
                "error": "No scraped content provided"
            }
        
        documents = []
        metadatas = []
        
        for url, content in scraped_content.items():
            # Split content into chunks (max 1000 chars per chunk)
            chunk_size = 1000
            chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "url": url,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source_type": "web_scrape",
                    "saved_at": datetime.now().isoformat()
                })
        
        # Save to RAG store
        result = create_documents(documents=documents, metadatas=metadatas)
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save scraped content: {str(e)}"
        }


# ========================================
# BACKWARD COMPATIBILITY
# ========================================

def add_documents(documents: List[str]) -> Dict[str, Any]:
    """Backward compatibility function"""
    return create_documents(documents)