import os
import sys
import json
import time
import requests
from typing import List, Dict, Any, Optional, Generator
from rich.console import Console

# Internal imports
from src.db import search_chunks
from src.embedder import Embedder

console = Console()

class RAGQuery:
    """Handles retrieval and communication with the Ollama LLM."""
    
    def __init__(self, db_conn, embedder: Embedder):
        self.db_conn = db_conn
        self.embedder = embedder
        
        # Load from environment variables
        self.model_name = os.environ.get("MODEL_NAME", "llama3.1:8b-instruct-q4_K_M")
        self.ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip('/')
        
        # Auto-detect model family for parameters
        self.is_large_model = '70b' in self.model_name.lower() or '72b' in self.model_name.lower()
        
        if self.is_large_model:
            self.top_k = int(os.getenv('RAG_TOP_K', '5'))
        else:
            self.top_k = int(os.getenv('RAG_TOP_K', '10'))
            
        self.llm_temp = float(os.getenv('LLM_TEMP', '0.0'))
        self.llm_ctx = int(os.getenv('LLM_CTX', '4096' if not self.is_large_model else '16384'))
        self.llm_num_predict = int(os.getenv('LLM_NUM_PREDICT', '512' if not self.is_large_model else '1024'))

    def get_system_prompt(self) -> str:
        """Returns the system prompt based on the model size."""
        if not self.is_large_model:
            # ULTRA_STRICT for 8B models
            return (
                "You are a document retrieval assistant for GKN Aerospace.\n"
                "You have been given context excerpts from internal documents.\n"
                "RULES — follow every rule exactly:\n"
                "1. Answer using ONLY information stated in the context excerpts.\n"
                "2. DO NOT use knowledge from your training.\n"
                "3. DO NOT guess, infer, or extrapolate.\n"
                "4. DO NOT add background information even if you believe it is correct.\n"
                "5. For every fact you state, cite the source: [Source: filename]\n"
                "6. If the answer is not in the context, respond with this exact phrase:\n"
                "   \"I cannot find this information in the provided documents.\"\n"
                "7. Say nothing else when using rule 6. No apology. No explanation.\n"
                "EXAMPLE OF CORRECT BEHAVIOUR:\n"
                "Context: === Source 1: service_config.yaml === api-gateway: port: 8080\n"
                "Question: What port does the api-gateway use?\n"
                "Answer: The api-gateway uses port 8080. [Source: service_config.yaml]"
            )
        else:
            # STRICT for 70B models
            return (
                "You are a technical assistant for GKN Aerospace.\n"
                "Answer using ONLY the provided context.\n"
                "If not in context: \"I cannot find this information in the provided documents.\"\n"
                "Cite your source for each answer."
            )

    def retrieve(self, question: str, file_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves top_k chunks for a given question."""
        embedding = self.embedder.embed_query(question)
        return search_chunks(self.db_conn, embedding, top_k=self.top_k, file_type_filter=file_type_filter)

    def format_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Formats retrieved chunks into a standard context block."""
        formatted_parts = []
        for i, chunk in enumerate(chunks):
            filename = chunk.get('filename', 'Unknown')
            file_type = chunk.get('file_type', 'Unknown')
            relevance = chunk.get('similarity_score', 0.0)
            content = chunk.get('content', '')
            
            source_header = f"=== Source {i+1} (relevance: {relevance:.2f}): {filename} [{file_type}] ==="
            formatted_parts.append(f"{source_header}\n{content}")
            
        return "\n".join(formatted_parts)

    def ask(self, question: str, file_type_filter: Optional[str] = None) -> Dict[str, Any]:
        """Performs a full RAG query: retrieve context and ask the LLM."""
        start_time = time.perf_counter()
        
        chunks = self.retrieve(question, file_type_filter)
        context_block = self.format_context(chunks)
        combined_input = f"{context_block}\n\nQuestion: {question}"
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": combined_input}
            ],
            "stream": False,
            "options": {
                "temperature": self.llm_temp,
                "num_ctx": self.llm_ctx,
                "num_predict": self.llm_num_predict
            }
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            return {
                "answer": result['message']['content'],
                "sources": [c['filename'] for c in chunks],
                "scores": [c['similarity_score'] for c in chunks],
                "model_used": self.model_name,
                "top_k_used": self.top_k,
                "latency_ms": latency_ms
            }
        except Exception as e:
            console.print(f"[bold red]LLM Error:[/bold red] {e}")
            raise

    def ask_streaming(self, question: str, file_type_filter: Optional[str] = None) -> Generator[Any, None, None]:
        """Performs a RAG query and yields the LLM response delta."""
        start_time = time.perf_counter()
        
        chunks = self.retrieve(question, file_type_filter)
        context_block = self.format_context(chunks)
        combined_input = f"{context_block}\n\nQuestion: {question}"
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": combined_input}
            ],
            "stream": True,
            "options": {
                "temperature": self.llm_temp,
                "num_ctx": self.llm_ctx,
                "num_predict": self.llm_num_predict
            }
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/chat", json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    chunk_json = json.loads(line)
                    if 'message' in chunk_json:
                        yield chunk_json['message']['content']
                    
                    if chunk_json.get('done'):
                        latency_ms = int((time.perf_counter() - start_time) * 1000)
                        yield {
                            "done": True, 
                            "model_used": self.model_name, 
                            "latency_ms": latency_ms,
                            "top_k_used": self.top_k
                        }
        except Exception as e:
            console.print(f"[bold red]LLM Streaming Error:[/bold red] {e}")
            raise

    def hallucination_test(self) -> Dict[str, Any]:
        """Self-test to check if the model respects negative context."""
        question = "What is the boiling point of water in Celsius?"
        # Empty context
        combined_input = "Context: (No provided context excerpts)\n\nQuestion: " + question
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": combined_input}
            ],
            "stream": False,
            "options": {"temperature": 0.0}
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=60)
            response.raise_for_status()
            content = response.json()['message']['content']
            
            passed = "I cannot find this information" in content
            return {"passed": passed, "response": content}
        except Exception as e:
            return {"passed": False, "response": str(e)}

if __name__ == "__main__":
    import argparse
    from src.db import DatabaseConnection
    
    parser = argparse.ArgumentParser(description="GKN Aerospace RAG Query CLI")
    parser.add_argument("question", nargs="?", help="The question to ask.")
    parser.add_argument("--type", help="Filter by file type (e.g., .yaml, .docx).")
    parser.add_argument("--stream", action="store_true", help="Enable streaming output.")
    parser.add_argument("--hallucination-test", action="store_true", help="Run hallucination check.")
    parser.add_argument("--show-sources", action="store_true", help="Show retrieved chunks without asking LLM.")
    
    args = parser.parse_args()
    
    try:
        embedder = Embedder()
        with DatabaseConnection() as conn:
            rag = RAGQuery(conn, embedder)
            
            if args.hallucination_test:
                console.print("[bold yellow]Running Hallucination Test...[/bold yellow]")
                test_result = rag.hallucination_test()
                status = "[bold green]PASSED[/bold green]" if test_result['passed'] else "[bold red]FAILED[/bold red]"
                console.print(f"Status: {status}")
                console.print(f"Model Response: {test_result['response']}")
                sys.exit(0)
                
            if not args.question:
                parser.print_help()
                sys.exit(0)
                
            if args.show_sources:
                chunks = rag.retrieve(args.question, file_type_filter=args.type)
                console.print(rag.format_context(chunks))
                sys.exit(0)
                
            if args.stream:
                console.print("[bold blue]Response:[/bold blue]")
                for delta in rag.ask_streaming(args.question, file_type_filter=args.type):
                    if isinstance(delta, str):
                        print(delta, end="", flush=True)
                    else:
                        console.print(f"\n\n[dim]Model: {delta['model_used']} | Latency: {delta['latency_ms']}ms[/dim]")
                print()
            else:
                result = rag.ask(args.question, file_type_filter=args.type)
                console.print("\n[bold blue]Answer:[/bold blue]")
                console.print(result['answer'])
                console.print(f"\n[dim]Model: {result['model_used']} | Sources: {', '.join(result['sources'])} | Latency: {result['latency_ms']}ms[/dim]")
                
    except Exception as e:
        console.print(f"[bold red]Fatal Error:[/bold red] {e}")
