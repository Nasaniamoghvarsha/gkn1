from src.db import DatabaseConnection
from rich.console import Console

console = Console()

def debug_tables():
    with DatabaseConnection() as conn:
        with conn.cursor() as cur:
            console.print("[bold yellow]--- Documents ---[/bold yellow]")
            cur.execute("SELECT id, filename, file_type FROM documents")
            docs = cur.fetchall()
            doc_ids = set()
            for doc in docs:
                console.print(f"ID: {doc[0]} | File: {doc[1]} ({doc[2]})")
                doc_ids.add(doc[0])
            
            console.print("\n[bold yellow]--- Chunks ---[/bold yellow]")
            cur.execute("SELECT id, document_id, chunk_index, LEFT(content, 30) FROM chunks LIMIT 10")
            chunks = cur.fetchall()
            for ch in chunks:
                matched = "YES" if ch[1] in doc_ids else "NO"
                console.print(f"ID: {ch[0]} | DocID: {ch[1]} | Matching Doc: {matched} | Content: {ch[3]}")

if __name__ == "__main__":
    debug_tables()
