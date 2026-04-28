import os
import uuid
import logging
from typing import List

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.utils import embedding_functions
    
    # Store locally in the backend directory
    CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_data")
    
    # Initialize client
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    
    # Use standard default sentence-transformers embedding
    sentence_transformer_ef = embedding_functions.DefaultEmbeddingFunction()

except ImportError:
    logger.warning("ChromaDB is not installed or failed to initialize. RAG features will be bypassed.")
    chroma_client = None


def ingest_document(course_id: int, text: str) -> bool:
    """
    Chunks a massive document and embeds it locally via ChromaDB.
    This saves us from passing a 50-page PDF directly to Gemini.
    """
    if not chroma_client:
        return False
        
    try:
        collection = chroma_client.get_or_create_collection(
            name=f"course_{course_id}", 
            embedding_function=sentence_transformer_ef
        )
        
        # Simple chunking logic (approx 500 words)
        words = text.split()
        chunk_size = 500
        chunks = []
        ids = []
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            chunks.append(chunk)
            ids.append(str(uuid.uuid4()))
            
        collection.add(
            documents=chunks,
            ids=ids,
            metadatas=[{"chunk_index": i} for i in range(len(chunks))]
        )
        return True
    except Exception as e:
        logger.error(f"Failed to ingest document into ChromaDB: {e}")
        return False


def retrieve_context(course_id: int, query: str, n_results: int = 3) -> str:
    """
    Retrieves the top N most relevant chunks for a specific query.
    Used by TopicAgent to fetch narrow context without burning massive tokens.
    """
    if not chroma_client:
        return ""
        
    try:
        collection = chroma_client.get_collection(
            name=f"course_{course_id}",
            embedding_function=sentence_transformer_ef
        )
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        if results and results["documents"]:
            # Combine the retrieved chunks
            return "\n\n".join(results["documents"][0])
            
        return ""
    except Exception as e:
        logger.error(f"Failed to retrieve context from ChromaDB: {e}")
        return ""
