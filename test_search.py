from src.db import DatabaseConnection
from src.embedder import Embedder
from src.query import RAGQuery
from rich.console import Console

console = Console()

def test_search():
    import os
    embedder = Embedder()
    query = "what image is used for the api service?"
    
    with DatabaseConnection() as conn:
        rag = RAGQuery(conn, embedder)
        console.print(f"[dim]RAG TopK: {rag.top_k}[/dim]")
        
        result = rag.ask(query)
        console.print(f"\n[bold blue]Answer:[/bold blue]\n{result['answer']}")
        console.print(f"\n[dim]Sources: {result['sources']}[/dim]")
        console.print(f"[dim]Scores: {result['scores']}[/dim]")

if __name__ == "__main__":
    test_search()

if __name__ == "__main__":
    test_search()
