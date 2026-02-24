import psycopg2
from src.db import DatabaseConnection
from rich.console import Console

console = Console()

def setup_database():
    """Initializes the PostgreSQL database with the required schema and pgvector extension."""
    console.print("[bold blue]Initializing GKN Aerospace RAG Database...[/bold blue]")
    
    with DatabaseConnection() as conn:
        with conn.cursor() as cur:
            # 1. Enable pgvector
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                console.print("  [green]✓[/green] Extension 'vector' enabled")
            except Exception as e:
                console.print(f"  [red]✗[/red] Failed to enable 'vector': {e}")
                return False

            # 2. Create Documents Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            console.print("  [green]✓[/green] Table 'documents' ready")

            # 3. Create Chunks Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id UUID PRIMARY KEY,
                    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    metadata JSONB,
                    embedding VECTOR(768),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            console.print("  [green]✓[/green] Table 'chunks' ready")

            # 4. Create Ingestion Logs Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_logs (
                    id SERIAL PRIMARY KEY,
                    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    chunks_created INTEGER,
                    error_message TEXT,
                    duration_ms INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            console.print("  [green]✓[/green] Table 'ingestion_logs' ready")

            # 5. Search Index
            # Note: ivfflat index is commented out for Phase 1 as it is not suitable for small datasets (< 1000 rows)
            # and may cause empty results. Sequential scan is faster and more accurate for this volume.
            # cur.execute("""
            #     CREATE INDEX IF NOT EXISTS chunk_vector_idx ON chunks 
            #     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
            # """)
            # console.print("  [green]✓[/green] Search index ready (deferred)")

            conn.commit()
            
    console.print("[bold green]Database Initialization Complete![/bold green]")
    return True

if __name__ == "__main__":
    setup_database()
