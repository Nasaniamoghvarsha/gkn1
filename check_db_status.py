from src.db import DatabaseConnection
from rich.console import Console

console = Console()

def check_db():
    with DatabaseConnection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM documents")
            doc_count = cur.fetchone()[0]
            
            cur.execute("SELECT count(*) FROM chunks")
            chunk_count = cur.fetchone()[0]
            
            cur.execute("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL")
            embed_count = cur.fetchone()[0]
            
            cur.execute("SELECT filename, file_type FROM documents")
            docs = cur.fetchall()
            
            console.print(f"Documents in DB: {doc_count}")
            for doc in docs:
                console.print(f"  - {doc[0]} ({doc[1]})")
            console.print(f"Total Chunks: {chunk_count}")
            console.print(f"Embedded Chunks: {embed_count}")

if __name__ == "__main__":
    check_db()
