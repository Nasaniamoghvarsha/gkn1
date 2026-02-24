import sys
import os
import yaml
from typing import List, Dict, Any
import tiktoken
from rich.console import Console

console = Console()

def get_token_count(text: str, encoding_name: str = "cl100k_base") -> int:
    """Calculates token count for a string using tiktoken."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))

def parse_yaml(file_path: str) -> List[Dict[str, Any]]:
    """Parses a YAML file, handling multi-document and specialized splitting (Docker Compose, K8s)."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        return []

    filename = os.path.basename(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Use safe_load_all for multi-document YAML
            docs = list(yaml.safe_load_all(f))
    except Exception as e:
        console.print(f"[bold red]Error loading YAML:[/bold red] {e}")
        return []

    all_chunks = []
    chunk_index = 0

    for doc in docs:
        if not doc:
            continue
            
        doc_content = yaml.dump(doc, sort_keys=False, indent=2)
        doc_tokens = get_token_count(doc_content)
        
        if doc_tokens <= 400:
            # Case 1: Small document
            all_chunks.append({
                'content': doc_content,
                'token_count': doc_tokens,
                'chunk_metadata': {
                    'file_type': 'yaml',
                    'yaml_kind': doc.get('kind') if isinstance(doc, dict) else None,
                    'resource_name': doc.get('metadata', {}).get('name') if isinstance(doc, dict) else None,
                    'chunk_index': chunk_index
                }
            })
            chunk_index += 1
        elif isinstance(doc, dict) and 'services' in doc:
            # Case 2: Docker Compose
            services = doc.get('services', {})
            for svc_name, svc_config in services.items():
                content = f"docker-compose: {filename} | service: {svc_name}\n"
                content += yaml.dump({svc_name: svc_config}, sort_keys=False, indent=2)
                all_chunks.append({
                    'content': content,
                    'token_count': get_token_count(content),
                    'chunk_metadata': {
                        'file_type': 'yaml',
                        'yaml_kind': 'DockerComposeService',
                        'resource_name': svc_name,
                        'chunk_index': chunk_index
                    }
                })
                chunk_index += 1
        elif isinstance(doc, dict) and 'kind' in doc:
            # Case 3: Kubernetes or similar with 'kind'
            kind = doc.get('kind')
            name = doc.get('metadata', {}).get('name', 'unnamed')
            all_chunks.append({
                'content': doc_content,
                'token_count': doc_tokens,
                'chunk_metadata': {
                    'file_type': 'yaml',
                    'yaml_kind': kind,
                    'resource_name': name,
                    'chunk_index': chunk_index
                }
            })
            chunk_index += 1
        elif isinstance(doc, dict):
            # Case 4: Large dict - split by top-level keys
            for key, value in doc.items():
                content = f"File: {filename} | Key: {key}\n"
                content += yaml.dump({key: value}, sort_keys=False, indent=2)
                all_chunks.append({
                    'content': content,
                    'token_count': get_token_count(content),
                    'chunk_metadata': {
                        'file_type': 'yaml',
                        'yaml_kind': 'TopLevelKey',
                        'resource_name': key,
                        'chunk_index': chunk_index
                    }
                })
                chunk_index += 1
        else:
            # Fallback
            all_chunks.append({
                'content': doc_content,
                'token_count': doc_tokens,
                'chunk_metadata': {
                    'file_type': 'yaml',
                    'yaml_kind': None,
                    'resource_name': None,
                    'chunk_index': chunk_index
                }
            })
            chunk_index += 1

    return all_chunks

if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold yellow]Usage:[/bold yellow] python src/parsers/yaml_parser.py <path_to_yaml>")
    else:
        file_path = sys.argv[1]
        results = parse_yaml(file_path)
        console.print(f"\n[bold green]Parsed {len(results)} chunks from:[/bold green] {file_path}")
        for i, chunk in enumerate(results[:2]):
            console.print(f"\n[bold cyan]--- Chunk {i} ---[/bold cyan]")
            console.print(f"[bold]Metadata:[/bold] {chunk['chunk_metadata']}")
            console.print(f"[bold]Tokens:[/bold] {chunk['token_count']}")
            console.print(f"[bold]Content Preview:[/bold]\n{chunk['content'][:300]}...")
