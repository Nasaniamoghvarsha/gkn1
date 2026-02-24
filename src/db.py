import os
import uuid
import logging
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv
from rich.console import Console

# Load environment variables with override to prevent host-level shadowing
load_dotenv(override=True)

console = Console()
logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Context manager for PostgreSQL database connections."""
    
    def __init__(self):
        self.host = os.environ.get("DB_HOST", "localhost")
        self.port = os.environ.get("DB_PORT", "5432")
        self.name = os.environ.get("DB_NAME", "gkn_rag")
        self.user = os.environ.get("DB_USER", "raguser")
        self.password = os.environ.get("DB_PASSWORD")
        self.conn = None

    def __enter__(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.name,
                user=self.user,
                password=self.password
            )
            # Register pgvector for the connection
            register_vector(self.conn)
            return self.conn
        except Exception as e:
            console.print(f"[bold red]Error connecting to database:[/bold red] {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    @staticmethod
    def health_check() -> bool:
        """Returns True if a connection can be established."""
        try:
            with DatabaseConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception:
            return False

def insert_document(conn, filename: str, file_type: str, file_path: str, file_hash: str, metadata: Dict[str, Any]) -> uuid.UUID:
    """Inserts a document or returns existing ID if hash exists."""
    with conn.cursor() as cur:
        # Check for existing hash
        cur.execute("SELECT id FROM documents WHERE file_hash = %s", (file_hash,))
        existing = cur.fetchone()
        if existing:
            return existing[0]

        # Insert new document
        doc_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO documents (id, filename, file_type, file_path, file_hash, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (str(doc_id), filename, file_type, file_path, file_hash, psycopg2.extras.Json(metadata))
        )
        conn.commit()
        return doc_id

def insert_chunk(conn, document_id: uuid.UUID, chunk_index: int, content: str, token_count: int, chunk_metadata: Dict[str, Any]) -> uuid.UUID:
    """Inserts a chunk without embedding."""
    with conn.cursor() as cur:
        chunk_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO chunks (id, document_id, chunk_index, content, token_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (str(chunk_id), str(document_id), chunk_index, content, token_count, psycopg2.extras.Json(chunk_metadata))
        )
        conn.commit()
        return chunk_id

def update_chunk_embedding(conn, chunk_id: uuid.UUID, embedding_vector: List[float], embed_model: str) -> None:
    """Updates the embedding for a specific chunk."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE chunks SET embedding = %s, metadata = metadata || %s WHERE id = %s",
            (embedding_vector, psycopg2.extras.Json({"embedding_model": embed_model}), str(chunk_id))
        )
        conn.commit()

def search_chunks(conn, query_embedding: List[float], top_k: int = 5, file_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Performs cosine similarity search using pgvector."""
    # Convert embedding to a string format [0.1, 0.2, ...] for robust casting
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
    
    query = """
        SELECT 
            c.id, 
            c.content, 
            c.metadata as chunk_metadata, 
            d.filename, 
            d.file_type,
            1 - (c.embedding <=> %s::vector) AS similarity_score
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
    """
    params = [embedding_str]
    
    if file_type_filter:
        query += " AND d.file_type = %s"
        params.append(file_type_filter)
        
    query += " ORDER BY c.embedding <=> %s::vector LIMIT %s"
    params.extend([embedding_str, top_k])

    with conn.cursor() as cur:
        cur.execute(query, params)
        results = cur.fetchall()
        
        # Manual mapping for standard cursor
        formatted = []
        for row in results:
            formatted.append({
                "id": str(row[0]),
                "content": row[1],
                "chunk_metadata": row[2],
                "filename": row[3],
                "file_type": row[4],
                "similarity_score": float(row[5])
            })
        return formatted

def log_ingestion(conn, document_id: uuid.UUID, status: str, chunks_created: int, error_message: Optional[str], duration_ms: int) -> None:
    """Logs ingestion telemetry."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_logs (document_id, status, chunks_created, error_message, duration_ms)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (str(document_id), status, chunks_created, error_message, duration_ms)
        )
        conn.commit()

if __name__ == "__main__":
    console.print("[bold blue]Testing Database Connection...[/bold blue]")
    if DatabaseConnection.health_check():
        console.print("[bold green]Connection Successful![/bold green]")
    else:
        console.print("[bold red]Connection Failed! Please check your .env settings.[/bold red]")
