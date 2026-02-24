from src.db import DatabaseConnection
from rich.console import Console

console = Console()

def drop_index():
    with DatabaseConnection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP INDEX IF EXISTS chunk_vector_idx")
            conn.commit()
            console.print("[green]Index dropped![/green]")

if __name__ == "__main__":
    drop_index()
