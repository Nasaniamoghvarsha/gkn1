from src.db import DatabaseConnection
from src.embedder import Embedder
from rich.console import Console

console = Console()

def debug_retrieval():
    embedder = Embedder()
    query = "What is the security protocol for GKN Aerospace?"
    qvec = embedder.embed_query(query)
    qstr = "[" + ",".join(map(str, qvec)) + "]"
    
    with DatabaseConnection() as conn:
        with conn.cursor() as cur:
            # 1. Raw Chunks
            cur.execute("SELECT count(*) FROM chunks")
            console.print(f"Chunks in table: {cur.fetchone()[0]}")
            
            # 2. Raw Join check
            cur.execute("SELECT count(*) FROM chunks c JOIN documents d ON c.document_id = d.id")
            console.print(f"Joined Rows: {cur.fetchone()[0]}")
            
            # 3. Full Search with JOIN (No Index)
            query = """
                SELECT 
                    c.id, 
                    d.filename,
                    1 - (c.embedding <=> %s::vector) AS similarity_score
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %s::vector
                LIMIT 5
            """
            cur.execute(query, (qstr, qstr))
            rows = cur.fetchall()
            console.print(f"\nFull JOIN Search (No Index) Results: {len(rows)}")
            for r in rows:
                console.print(f"File: {r[1]} | Sim: {r[2]:.4f} | ID: {r[0]}")

if __name__ == "__main__":
    debug_retrieval()
