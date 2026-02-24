from src.db import DatabaseConnection
from rich.console import Console

console = Console()

def reset_database():
    """Wipes all data from documents and chunks for a clean validation state."""
    console.print("[bold red]Wiping Database for clean validation...[/bold red]")
    with DatabaseConnection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE documents CASCADE")
            conn.commit()
    console.print("[bold green]✓ Database wiped.[/bold green]")

if __name__ == "__main__":
    reset_database()
