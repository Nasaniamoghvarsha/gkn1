import sys
import os
import json
from typing import List, Dict, Any
import tiktoken
from rich.console import Console

console = Console()

def get_token_count(text: str, encoding_name: str = "cl100k_base") -> int:
    """Calculates token count for a string using tiktoken."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))

def parse_json(file_path: str) -> List[Dict[str, Any]]:
    """Parses a JSON file using token-aware splitting logic."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        return []

    filename = os.path.basename(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Error loading JSON:[/bold red] {e}")
        return []

    full_content = json.dumps(data, indent=2)
    total_tokens = get_token_count(full_content)
    
    chunks = []
    chunk_index = 0

    if total_tokens <= 200:
        # Case 1: Small file
        chunks.append({
            'content': full_content,
            'token_count': total_tokens,
            'chunk_metadata': {
                'file_type': 'json',
                'top_level_key': None,
                'is_array': isinstance(data, list),
                'chunk_index': chunk_index
            }
        })
    elif isinstance(data, dict):
        # Case 2: Large dict - split by top-level keys
        for key, value in data.items():
            content = f"File: {filename} | Key: {key}\n{json.dumps(value, indent=2)}"
            chunks.append({
                'content': content,
                'token_count': get_token_count(content),
                'chunk_metadata': {
                    'file_type': 'json',
                    'top_level_key': key,
                    'is_array': False,
                    'chunk_index': chunk_index
                }
            })
            chunk_index += 1
    elif isinstance(data, list):
        # Case 3: Large list
        if len(data) <= 10:
            chunks.append({
                'content': full_content,
                'token_count': total_tokens,
                'chunk_metadata': {
                    'file_type': 'json',
                    'top_level_key': None,
                    'is_array': True,
                    'chunk_index': chunk_index
                }
            })
        else:
            # Chunks of 10 items
            for i in range(0, len(data), 10):
                batch = data[i:i+10]
                j = i + len(batch) - 1
                content = f"File: {filename} | Items [{i}-{j}]\n{json.dumps(batch, indent=2)}"
                chunks.append({
                    'content': content,
                    'token_count': get_token_count(content),
                    'chunk_metadata': {
                        'file_type': 'json',
                        'top_level_key': None,
                        'is_array': True,
                        'chunk_index': chunk_index
                    }
                })
                chunk_index += 1
    else:
        # Fallback for primitives or other types if they were large (unlikely)
        chunks.append({
            'content': full_content,
            'token_count': total_tokens,
            'chunk_metadata': {
                'file_type': 'json',
                'top_level_key': None,
                'is_array': False,
                'chunk_index': chunk_index
            }
        })

    return chunks

if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold yellow]Usage:[/bold yellow] python src/parsers/json_parser.py <path_to_json>")
    else:
        file_path = sys.argv[1]
        results = parse_json(file_path)
        console.print(f"\n[bold green]Parsed {len(results)} chunks from:[/bold green] {file_path}")
        for i, chunk in enumerate(results[:2]):
            console.print(f"\n[bold cyan]--- Chunk {i} ---[/bold cyan]")
            console.print(f"[bold]Metadata:[/bold] {chunk['chunk_metadata']}")
            console.print(f"[bold]Tokens:[/bold] {chunk['token_count']}")
            console.print(f"[bold]Content Preview:[/bold]\n{chunk['content'][:300]}...")
