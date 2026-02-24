import sys
import argparse
import requests
import json
import os
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel

console = Console()
BASE_URL = "http://localhost:8001"

def check_connection():
    try:
        requests.get(f"{BASE_URL}/health", timeout=10)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        console.print("[bold red]CRITICAL: Cannot connect to the RAG Core. Ensure FastAPI is running on localhost:8000 and has initialized the models.[/bold red]")
        sys.exit(1)

def handle_health(args):
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        table = Table(title="GKN Aerospace RAG Core - Health Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="magenta")

        table.add_row("API Gateway", "HEALTHY", f"Port: 8000")
        table.add_row("Database", data.get("db", "UNKNOWN"), "PostgreSQL (pgvector)")
        table.add_row("LLM Model", "ACTIVE", data.get("model", "UNKNOWN"))
        table.add_row("Server Time", "OK", str(data.get("timestamp", "")))

        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error fetching health status:[/bold red] {e}")

def handle_ingest(args):
    if not os.path.exists(args.file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {args.file_path}")
        return

    try:
        with open(args.file_path, "rb") as f:
            files = {"file": (os.path.basename(args.file_path), f)}
            with console.status(f"[bold blue]Ingesting {os.path.basename(args.file_path)}..."):
                resp = requests.post(f"{BASE_URL}/ingest", files=files, timeout=60)
                resp.raise_for_status()
                data = resp.json()

        if data.get("status") in ["success", "skipped"]:
            status_color = "green" if data["status"] == "success" else "yellow"
            console.print(f"[bold {status_color}]SUCCESS:[/bold {status_color}] Ingested {data['filename']}")
            console.print(f"Status: {data['status'].upper()}")
            console.print(f"Chunks Created: [bold cyan]{data.get('chunks_created', 0)}[/bold cyan]")
        else:
            console.print(f"[bold red]Ingestion Failed:[/bold red] {data.get('error', 'Unknown error')}")
    except Exception as e:
        console.print(f"[bold red]Error during ingestion:[/bold red] {e}")

def handle_ask(args):
    try:
        payload = {
            "question": args.question,
            "file_type_filter": args.type
        }
        with console.status("[bold green]Querying RAG Core..."):
            resp = requests.post(f"{BASE_URL}/query", json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

        console.print(Panel(Markdown(data["answer"]), title="[bold green]RAG Response", border_style="green"))

        if data.get("sources"):
            console.print("\n[bold cyan]Citations & Relevance:[/bold cyan]")
            for i, (source, score) in enumerate(zip(data["sources"], data["scores"])):
                console.print(f" {i+1}. [bold]{source}[/bold] (Score: [italic]{score:.4f}[/italic])")
    except Exception as e:
        console.print(f"[bold red]Error during query:[/bold red] {e}")

def handle_generate(args):
    try:
        payload = {
            "question": args.prompt,
            "language": args.lang
        }
        with console.status(f"[bold magenta]Agent is generating {args.lang} code..."):
            resp = requests.post(f"{BASE_URL}/generate/agent", json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()

        if data.get("is_incomplete"):
            console.print("[bold red]WARNING: Agent exceeded iteration limit. Code may be incomplete or invalid.[/bold red]")

        console.print(f"[bold magenta]Self-Correction Iterations:[/bold magenta] {data['iteration_count']}")
        
        syntax = Syntax(data["generated_code"], args.lang, theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=f"[bold cyan]Generated {args.lang.upper()}", border_style="cyan"))

        if data.get("errors"):
            console.print("\n[bold yellow]Remaining Validation Errors:[/bold yellow]")
            for error in data["errors"]:
                console.print(f" - Line {error['line']}: {error['message']}")
    except Exception as e:
        console.print(f"[bold red]Error during agent generation:[/bold red] {e}")

def main():
    parser = argparse.ArgumentParser(description="GKN Aerospace RAG CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Health command
    subparsers.add_parser("health", help="Check RAG Core health status")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a document")
    ingest_parser.add_argument("file_path", help="Path to the file (.docx, .pptx, .json, .yaml)")

    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask a question using RAG")
    ask_parser.add_argument("question", help="The question to ask")
    ask_parser.add_argument("--type", help="Filter by file type (e.g., .docx, .yaml)")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate code using Agentic Loop")
    gen_parser.add_argument("prompt", help="Code generation prompt")
    gen_parser.add_argument("--lang", default="python", help="Language for syntax highlighting (default: python)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    check_connection()

    if args.command == "health":
        handle_health(args)
    elif args.command == "ingest":
        handle_ingest(args)
    elif args.command == "ask":
        handle_ask(args)
    elif args.command == "generate":
        handle_generate(args)

if __name__ == "__main__":
    main()
