import time
import statistics
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import torch
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

class Embedder:
    """Handles text embeddings using nomic-embed-text-v1.5 on CPU."""
    
    def __init__(self, model_name: str = 'nomic-ai/nomic-embed-text-v1.5'):
        console.print(f"[bold blue]Loading embedding model:[/bold blue] {model_name} on CPU...")
        
        # Force CPU usage
        self.device = 'cpu'
        self.model = SentenceTransformer(
            model_name, 
            device=self.device,
            trust_remote_code=True
        )
        
        # Verify dimension
        self.dimension = 768
        test_output = self.model.encode(["test"])
        actual_dim = test_output.shape[1]
        
        assert actual_dim == self.dimension, f"Model dimension mismatch! Expected {self.dimension}, got {actual_dim}"
        
        console.print(f"[bold green]Model loaded successfully.[/bold green] Dimension: {self.dimension}")

    def embed_text(self, text: str) -> List[float]:
        """Embeds a single document string with 'search_document: ' prefix."""
        prefixed_text = f"search_document: {text}"
        embedding = self.model.encode(prefixed_text, convert_to_tensor=False)
        return embedding.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embeds a single query string with 'search_query: ' prefix."""
        prefixed_text = f"search_query: {text}"
        embedding = self.model.encode(prefixed_text, convert_to_tensor=False)
        return embedding.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embeds a list of texts in batches with a progress bar."""
        prefixed_texts = [f"search_document: {t}" for t in texts]
        
        embeddings = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Embedding batch...", total=len(prefixed_texts))
            
            for i in range(0, len(prefixed_texts), batch_size):
                batch = prefixed_texts[i:i + batch_size]
                batch_embeddings = self.model.encode(batch, convert_to_tensor=False)
                embeddings.extend(batch_embeddings.tolist())
                progress.update(task, advance=len(batch))
        
        return embeddings

    def benchmark(self) -> Dict[str, any]:
        """Benchmarks the embedding model with 10 test strings."""
        test_strings = [
            "GKN Aerospace is a global leader in aerostructures.",
            "Retrieval Augmented Generation improves LLM accuracy.",
            "PostgreSQL with pgvector provides efficient vector storage.",
            "Python 3.11 is used for this RAG pipeline.",
            "ITAR/EAR compliance is critical for aerospace data.",
            "Ollama runs local LLMs like Llama 3.",
            "Sentence transformers enable CPU-based embeddings.",
            "Chunking strategies depend on the file format.",
            "Document hashes prevent duplicate ingestion.",
            "Cosine similarity is used for semantic search."
        ]
        
        durations = []
        for text in test_strings:
            start_time = time.perf_counter()
            self.embed_text(text)
            end_time = time.perf_counter()
            durations.append((end_time - start_time) * 1000) # Convert to ms
            
        return {
            'p50_ms': round(statistics.median(durations), 2),
            'p95_ms': round(statistics.quantiles(durations, n=20)[18], 2) if len(durations) >= 20 else round(max(durations), 2),
            'dimension': self.dimension
        }

if __name__ == "__main__":
    try:
        embedder = Embedder()
        console.print("\n[bold yellow]Running Benchmark...[/bold yellow]")
        results = embedder.benchmark()
        
        console.print("\n[bold cyan]Benchmark Results:[/bold cyan]")
        console.print(f"  - Model Dimension: {results['dimension']}")
        console.print(f"  - Median (p50) Latency: {results['p50_ms']} ms")
        console.print(f"  - p95 Latency: {results['p95_ms']} ms")
    except Exception as e:
        console.print(f"[bold red]Failed to run embedder:[/bold red] {e}")
