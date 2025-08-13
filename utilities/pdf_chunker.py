import requests
import tempfile
import os
from typing import List, Dict, Any
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document


def ingest_pdf_and_chunk(
    url: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separator: str = "\n\n"
) -> List[Dict[str, Any]]:
    """
    Download a PDF from URL, extract text, chunk it using LangChain, 
    and format for procedural memory store.
    
    Args:
        url: URL of the PDF to download
        chunk_size: Maximum size of each chunk
        chunk_overlap: Number of characters to overlap between chunks
        separator: Primary separator for splitting text
    
    Returns:
        List of dictionaries formatted for procedural_memory_store.put()
    """
    
    # Step 1: Download PDF to temporary file
    print(f"Downloading PDF from {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        temp_file_path = temp_file.name
    
    try:
        # Step 2: Load PDF using LangChain
        print("Loading PDF with LangChain...")
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        
        # Step 3: Combine all pages into single text
        full_text = "\n\n".join([doc.page_content for doc in documents])
        
        # Step 4: Split text into chunks
        print("Chunking text...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[separator, "\n", " ", ""]
        )
        
        chunks = text_splitter.split_text(full_text)
        
        # Step 5: Format chunks for procedural memory store
        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            formatted_chunk = {
                "key": f"pdf_chunk_{i}",
                "value": {
                    "content": chunk,
                    "source": url,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            }
            formatted_chunks.append(formatted_chunk)
        
        print(f"Successfully created {len(formatted_chunks)} chunks")
        return formatted_chunks
        
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)


def store_chunks_in_memory(chunks: List[Dict[str, Any]], semantic_memory_store, category: str = "research_papers"):
    """
    Store the formatted chunks in the procedural memory store.
    
    Args:
        chunks: List of formatted chunks from ingest_pdf_and_chunk()
        procedural_memory_store: The memory store instance
        category: Category for organizing the chunks
    """
    print(f"Storing {len(chunks)} chunks in procedural memory...")
    
    for chunk in chunks:
        semantic_memory_store.put(
            (category,), 
            key=chunk["key"], 
            value=chunk["value"]
        )
    
    print("All chunks stored successfully!")


# Example usage function
def example_usage():
    """
    Example of how to use the functions with the provided URL
    """
    url = "https://arxiv.org/pdf/2404.13501"
    
    # Assuming you have your procedural_memory_store initialized
    # procedural_memory_store = YourMemoryStore()
    
    try:
        # Ingest and chunk the PDF
        chunks = ingest_pdf_and_chunk(url)
        
        # Store in memory (uncomment when you have the memory store)
        # store_chunks_in_memory(chunks, procedural_memory_store, "agent_memory_survey")
        
        # Print first chunk as example
        if chunks:
            print("\nFirst chunk example:")
            print(f"Key: {chunks[0]['key']}")
            print(f"Content preview: {chunks[0]['value']['content'][:200]}...")
            
        return chunks
        
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return []


if __name__ == "__main__":
    example_usage()
