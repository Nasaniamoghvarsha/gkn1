import os
import sys
import hashlib
import json
import time
from typing import List, Dict, Any, Optional
import uuid
import logging
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Internal imports
from src.db import DatabaseConnection, insert_document, insert_chunk, update_chunk_embedding, log_ingestion
from src.embedder import Embedder
from src.parsers.docx_parser import parse_docx
from src.parsers.pptx_parser import parse_pptx
from src.parsers.json_parser import parse_json
from src.parsers.yaml_parser import parse_yaml

console = Console()
logger = logging.getLogger(__name__)

def get_file_hash(file_path: str) -> str:
    """Computes the SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ingest_file(file_path: str, db_conn, embedder: Embedder) -> Dict[str, Any]:
    """Ingests a single file into the RAG system."""
    start_time = time.perf_counter()
    filename = os.path.basename(file_path)
    file_type = os.path.splitext(file_path)[1].lower()
    
    # 1. Compute Hash and Check for Duplicates
    file_hash = get_file_hash(file_path)
    
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM documents WHERE file_hash = %s", (file_hash,))
        if cur.fetchone():
            console.print(f"[yellow]Skipping {filename} — already ingested (unchanged)[/yellow]")
            return {"status": "skipped", "filename": filename, "chunks_created": 0}

    # 2. Route to correct parser
    try:
        if file_type == ".docx":
            chunks = parse_docx(file_path)
        elif file_type == ".pptx":
            chunks = parse_pptx(file_path)
        elif file_type == ".json":
            chunks = parse_json(file_path)
        elif file_type in [".yaml", ".yml"]:
            chunks = parse_yaml(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {file_type}")
    except Exception as e:
        error_msg = f"Parser error: {str(e)}"
        console.print(f"[bold red]Error parsing {filename}:[/bold red] {error_msg}")
        return {"status": "error", "filename": filename, "error": error_msg}

    if not chunks:
        return {"status": "empty", "filename": filename, "chunks_created": 0}

    # 3. Create Document Record
    # Metadata could include file stats
    doc_metadata = {
        "file_size": os.path.getsize(file_path),
        "extension": file_type
    }
    document_id = insert_document(db_conn, filename, file_type, file_path, file_hash, doc_metadata)

    # 4. Insert Chunks and Collect Content for Embedding
    chunk_ids = []
    chunk_contents = []
    
    for chunk in chunks:
        chunk_id = insert_chunk(
            db_conn, 
            document_id, 
            chunk['chunk_metadata'].get('chunk_index', 0), 
            chunk['content'], 
            chunk['token_count'], 
            chunk['chunk_metadata']
        )
        chunk_ids.append(chunk_id)
        chunk_contents.append(chunk['content'])

    # 5. Batch Embed Chunks
    console.print(f"[blue]Embedding {len(chunks)} chunks from {filename}...[/blue]")
    embeddings = embedder.embed_batch(chunk_contents)

    # 6. Update Chunks with Embeddings
    for cid, embedding in zip(chunk_ids, embeddings):
        update_chunk_embedding(db_conn, cid, embedding, "nomic-embed-text-v1.5")

    # 7. Update document with chunk count
    with db_conn.cursor() as cur:
        cur.execute("UPDATE documents SET metadata = metadata || %s WHERE id = %s", 
                   (json.dumps({"chunk_count": len(chunks)}), str(document_id)))
        db_conn.commit()

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    
    # 8. Log Ingestion
    log_ingestion(db_conn, document_id, "success", len(chunks), None, duration_ms)
    
    console.print(f"[green]Successfully ingested {filename} ({len(chunks)} chunks, {duration_ms}ms)[/green]")
    return {
        "status": "success", 
        "filename": filename, 
        "chunks_created": len(chunks), 
        "duration_ms": duration_ms
    }

def ingest_directory(dir_path: str) -> None:
    """Walks directory recursively and ingests supported files."""
    if not os.path.isdir(dir_path):
        console.print(f"[bold red]Error:[/bold red] {dir_path} is not a directory.")
        return

    supported_extensions = [".docx", ".pptx", ".json", ".yaml", ".yml"]
    
    try:
        embedder = Embedder()
        with DatabaseConnection() as conn:
            processed_count = 0
            created_count = 0
            skipped_count = 0
            error_count = 0
            
            for root, dirs, files in os.walk(dir_path):
                # Skip hidden and __pycache__
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != "__pycache__"]
                
                for file in files:
                    if file.startswith('.') or not any(file.lower().endswith(ext) for ext in supported_extensions):
                        continue
                        
                    file_path = os.path.join(root, file)
                    result = ingest_file(file_path, conn, embedder)
                    
                    if result["status"] == "success":
                        processed_count += 1
                        created_count += result["chunks_created"]
                    elif result["status"] == "skipped":
                        skipped_count += 1
                    else:
                        error_count += 1

            console.print("\n[bold cyan]Ingestion Summary:[/bold cyan]")
            console.print(f"  - Files Processed: {processed_count}")
            console.print(f"  - Chunks Created:  {created_count}")
            console.print(f"  - Files Skipped:   {skipped_count}")
            if error_count > 0:
                console.print(f"  - Errors:          [bold red]{error_count}[/bold red]")
                
    except Exception as e:
        console.print(f"[bold red]Critical Ingestion Error:[/bold red] {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold yellow]Usage:[/bold yellow] python src/ingest.py <file_or_directory>")
    else:
        path = sys.argv[1]
        if os.path.isdir(path):
            ingest_directory(path)
        elif os.path.isfile(path):
            try:
                embedder = Embedder()
                with DatabaseConnection() as conn:
                    ingest_file(path, conn, embedder)
            except Exception as e:
                console.print(f"[bold red]Failed to ingest file:[/bold red] {e}")
        else:
            console.print(f"[bold red]Error:[/bold red] Path not found: {path}")
