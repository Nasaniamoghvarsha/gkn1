import sys
import os
import argparse
import numpy as np
from typing import List, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import ProgressBar

# Internal imports
from src.db import DatabaseConnection, search_chunks
from src.embedder import Embedder

console = Console()

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def show_chunks(document_filename: str):
    """Inspects all chunks for a specific document."""
    try:
        with DatabaseConnection() as conn:
            with conn.cursor(cursor_factory=None) as cur:
                # First get doc_id
                cur.execute("SELECT id FROM documents WHERE filename = %s", (document_filename,))
                doc = cur.fetchone()
                if not doc:
                    console.print(f"[bold red]Error:[/bold red] Document '{document_filename}' not found in DB.")
                    return
                
                doc_id = doc[0]
                
                # Get chunks
                cur.execute(
                    "SELECT id, chunk_index, content, token_count, metadata FROM chunks WHERE document_id = %s ORDER BY chunk_index",
                    (doc_id,)
                )
                chunks = cur.fetchall()
                
                if not chunks:
                    console.print(f"[yellow]No chunks found for document '{document_filename}'.[/yellow]")
                    return

                table = Table(title=f"Chunks for {document_filename}")
                table.add_column("Idx", justify="right", style="cyan")
                table.add_column("Tokens", justify="right")
                table.add_column("Preview", style="dim")
                table.add_column("Metadata", style="italic")

                total_tokens = 0
                for row in chunks:
                    idx = row[1]
                    content_preview = row[2][:100].replace('\n', ' ') + "..."
                    tokens = row[3]
                    meta = str(row[4])
                    total_tokens += tokens
                    table.add_row(str(idx), str(tokens), content_preview, meta)

                console.print(table)
                console.print(f"\n[bold]Total Chunks:[/bold] {len(chunks)}")
                console.print(f"[bold]Average Token Count:[/bold] {total_tokens / len(chunks):.1f}")

    except Exception as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")

def test_retrieval(question: str, top_k=10):
    """Detailed retrieval analysis with visual similarity indicators."""
    try:
        embedder = Embedder()
        with DatabaseConnection() as conn:
            embedding = embedder.embed_query(question)
            results = search_chunks(conn, embedding, top_k=top_k)
            
            if not results:
                console.print("[yellow]No results found for the given query.[/yellow]")
                return

            console.print(Panel(f"[bold cyan]Question:[/bold cyan] {question}"))
            
            for i, res in enumerate(results):
                score = res['similarity_score']
                filename = res['filename']
                chunk_idx = res['chunk_metadata'].get('chunk_index', '?')
                content = res['content'][:200].replace('\n', ' ') + "..."
                
                # Similarity bar
                bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                color = "green" if score > 0.7 else "yellow" if score >= 0.5 else "red"
                
                header = f"[bold]Rank {i+1} | Score: {score:.4f} [[{color}]{bar}[/{color}]] | {filename} (Chunk {chunk_idx})[/bold]"
                
                if score < 0.5:
                    header += " [bold red]LOW RELEVANCE[/bold red]"
                
                console.print(header)
                console.print(f"[dim]{content}[/dim]")
                console.print(f"[italic]Metadata:[/italic] {res['chunk_metadata']}")
                console.print("-" * 50)

    except Exception as e:
        console.print(f"[bold red]Retrieval Error:[/bold red] {e}")

def compare_queries(question1: str, question2: str):
    """Side-by-side comparison of retrieved documents for two queries."""
    try:
        embedder = Embedder()
        with DatabaseConnection() as conn:
            # Query 1
            emb1 = embedder.embed_query(question1)
            res1 = search_chunks(conn, emb1, top_k=5)
            docs1 = {r['filename'] for r in res1}
            
            # Query 2
            emb2 = embedder.embed_query(question2)
            res2 = search_chunks(conn, emb2, top_k=5)
            docs2 = {r['filename'] for r in res2}
            
            table = Table(title="Query Comparison (Top 5 Documents)")
            table.add_column(f"Q1: {question1}", style="green")
            table.add_column(f"Q2: {question2}", style="cyan")
            
            # Find common and unique
            common = docs1.intersection(docs2)
            only1 = docs1 - docs2
            only2 = docs2 - docs1
            
            all_docs = sorted(list(docs1 | docs2))
            for doc in all_docs:
                col1 = f"✓ {doc}" if doc in docs1 else ""
                col2 = f"✓ {doc}" if doc in docs2 else ""
                
                # Highlight unique ones
                if doc in only1:
                    col1 = f"[bold yellow]{col1} (unique)[/bold yellow]"
                if doc in only2:
                    col2 = f"[bold yellow]{col2} (unique)[/bold yellow]"
                    
                table.add_row(col1, col2)
                
            console.print(table)
            
            overlap_pct = (len(common) / len(all_docs) * 100) if all_docs else 0
            console.print(f"\n[bold]Document Overlap:[/bold] {overlap_pct:.1f}%")

    except Exception as e:
        console.print(f"[bold red]Comparison Error:[/bold red] {e}")

def embedding_sanity_check():
    """Validates the embedding model using similarity pairs."""
    pairs = [
        # Similar
        ("GKN Aerospace makes plane parts.", "The company GKN produces aerostructures.", True),
        ("RAG uses a database for context.", "A retrieval system stores documents in a vector DB.", True),
        # Different
        ("Python 3.11 is fast.", "Apples are high in fiber.", False),
        ("The server uses port 8080.", "It is raining in Seattle.", False),
        ("ITAR compliance is mandatory.", "I like pizza with olives.", False)
    ]
    
    try:
        embedder = Embedder()
        console.print("[bold yellow]Running Embedding Sanity Check...[/bold yellow]")
        
        table = Table(show_header=True)
        table.add_column("Text A")
        table.add_column("Text B")
        table.add_column("Similarity")
        table.add_column("Status")
        
        failures = 0
        for t1, t2, should_be_similar in pairs:
            # For Nomic, we simulate query vs document for a realistic check
            v1 = embedder.embed_query(t1)
            v2 = embedder.embed_text(t2)
            sim = cosine_similarity(v1, v2)
            
            # Adjusted thresholds for nomic-embed-text-v1.5 which keeps high baseline similarity
            if should_be_similar:
                passed = (sim > 0.65)
                status = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL (Low Sim)[/bold red]"
            else:
                passed = (sim < 0.60)
                status = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL (High Sim)[/bold red]"
            
            if not passed:
                failures += 1
                
            table.add_row(t1[:30]+"...", t2[:30]+"...", f"{sim:.4f}", status)
            
        console.print(table)
        
        if failures > 0:
            console.print("[bold red]WARNING:[/bold red] Embedding model produced unexpected results. Check model loading and configuration.")
        else:
            console.print("[bold green]Sanity Check Passed![/bold green] Model is behaving correctly.")

    except Exception as e:
        console.print(f"[bold red]Sanity Check Error:[/bold red] {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GKN RAG Diagnostic Tools")
    subparsers = parser.add_subparsers(dest="command")
    
    # Chunks
    p_chunks = subparsers.add_parser("chunks")
    p_chunks.add_argument("filename")
    
    # Retrieve
    p_ret = subparsers.add_parser("retrieve")
    p_ret.add_argument("question")
    p_ret.add_argument("--top_k", type=int, default=10)
    
    # Compare
    p_comp = subparsers.add_parser("compare")
    p_comp.add_argument("q1")
    p_comp.add_argument("q2")
    
    # Sanity
    subparsers.add_parser("sanity")
    
    args = parser.parse_args()
    
    if args.command == "chunks":
        show_chunks(args.filename)
    elif args.command == "retrieve":
        test_retrieval(args.question, args.top_k)
    elif args.command == "compare":
        compare_queries(args.q1, args.q2)
    elif args.command == "sanity":
        embedding_sanity_check()
    else:
        parser.print_help()
