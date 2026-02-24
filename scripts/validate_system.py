import subprocess
import sys
import os
from typing import List, Tuple
from rich.console import Console
from rich.table import Table

console = Console()

def run_check(title: str, command: List[str] = None, expected_output: str = None, func=None) -> bool:
    """Runs a check, either via command or a Python function."""
    console.print(f"Checking: [cyan]{title}[/cyan]...", end=" ")
    
    try:
        output = ""
        success = False
        
        if func:
            success, output = func()
        elif command:
            # shell=False is safer; only use it if strictly necessary for shell features
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                shell=False
            )
            output = result.stdout + result.stderr
            success = (result.returncode == 0)
            
            if success and expected_output:
                success = expected_output.lower() in output.lower()
        
        if success:
            console.print("[bold green]PASS[/bold green]")
            return True
        else:
            console.print("[bold red]FAIL[/bold red]")
            console.print("-" * 40)
            console.print(f"[bold red]Result/Output:[/bold red]\n{output}")
            console.print("-" * 40)
            return False
            
    except Exception as e:
        console.print(f"[bold red]ERROR: {e}[/bold red]")
        return False

def check_env_model():
    """Native Python check for MODEL_NAME in .env"""
    if not os.path.exists(".env"):
        return False, "File .env not found."
    
    target = "llama3.1:8b-instruct-q4_K_M"
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("MODEL_NAME=") and target in line:
                    return True, line.strip()
        return False, f"MODEL_NAME not found or incorrect in .env (Expected {target})"
    except Exception as e:
        return False, str(e)

def validate_system():
    console.print(Table.grid(padding=(0, 1)))
    console.print("[bold reverse blue] GKN Aerospace RAG - Phase 1 System Validation [/bold reverse blue]\n")
    
    # 1. Infrastructure Checks
    if not run_check("ITAR Model Name in .env", func=check_env_model):
        sys.exit(1)
        
    infra_checks = [
        ("Database Connection", [sys.executable, "-m", "src.db"], "Connection successful"),
        ("Embedding Dimension", [sys.executable, "-m", "src.embedder"], "768")
    ]
    
    for title, cmd, expected in infra_checks:
        if not run_check(title, command=cmd, expected_output=expected):
            sys.exit(1)

    # 2. Ingestion Checks
    ingestion_checks = [
        ("Ingest DOCX", [sys.executable, "-m", "src.ingest", "tests/fixtures/sample.docx"], ""),
        ("Ingest YAML", [sys.executable, "-m", "src.ingest", "tests/fixtures/sample.yaml"], ""),
        ("Ingest PPTX", [sys.executable, "-m", "src.ingest", "tests/fixtures/sample.pptx"], ""),
        ("Deduplication Check", [sys.executable, "-m", "src.ingest", "tests/fixtures/sample.docx"], "already ingested")
    ]
    
    for title, cmd, expected in ingestion_checks:
        if not run_check(title, command=cmd, expected_output=expected):
            sys.exit(1)

    # 3. Retrieval & Diagnostics
    if not run_check("Embedding Sanity Check", command=[sys.executable, "-m", "src.debug_rag", "sanity"], expected_output="Sanity Check Passed"):
        sys.exit(1)

    # 4. Hallucination & Query Checks
    qa_checks = [
        ("Hallucination Resistance", [sys.executable, "-m", "src.query", "--hallucination-test"], "I cannot find this information"),
        ("Citation Enforcement", [sys.executable, "-m", "src.query", "what image is used for the api service?"], "[Source: sample.yaml]")
    ]
    
    for title, cmd, expected in qa_checks:
        if not run_check(title, command=cmd, expected_output=expected):
            sys.exit(1)

    # 5. Automated Test Suite
    # Note: using pytest might still need absolute path, but usually it's in scripts
    if not run_check("Full Integration Test Suite", command=[sys.executable, "-m", "pytest", "tests/test_rag.py", "-v", "-m", "integration"], expected_output="passed"):
        sys.exit(1)
            
    console.print(f"\n[bold green]SUCCESS: All checks passed![/bold green]")
    console.print("[bold green]System is functionally complete and compliant.[/bold green]")

if __name__ == "__main__":
    validate_system()
