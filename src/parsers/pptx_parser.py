import sys
import os
from typing import List, Dict, Any, Optional
from pptx import Presentation
import tiktoken
from rich.console import Console

console = Console()

def get_token_count(text: str, encoding_name: str = "cl100k_base") -> int:
    """Calculates token count for a string using tiktoken."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))

def parse_pptx(file_path: str) -> List[Dict[str, Any]]:
    """Parses a .pptx file, creating one or two chunks per slide."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        return []

    try:
        prs = Presentation(file_path)
    except Exception as e:
        console.print(f"[bold red]Error opening PPTX:[/bold red] {e}")
        return []

    chunks = []
    
    for i, slide in enumerate(prs.slides):
        slide_number = i + 1
        
        # 1. Slide Title
        slide_title = "[UNTITLED SLIDE]"
        if hasattr(slide, "shapes") and slide.shapes.title:
            slide_title = slide.shapes.title.text.strip() or slide_title
        
        title_prefix = f"[SLIDE {slide_number}: {slide_title}]\n"
        
        # 2. Content (Text and Images)
        content_lines = []
        has_images = False
        
        for shape in slide.shapes:
            # Text frames and boxes
            if hasattr(shape, "text_frame") and shape.text.strip():
                content_lines.append(shape.text.strip())
            
            # Images
            if shape.shape_type == 13: # Picture
                has_images = True
                # python-pptx doesn't have a direct 'alt_text' property in basic access,
                # but we can check description/name which are often used for alt text.
                alt_text = getattr(shape, "description", None) or getattr(shape, "name", None)
                if alt_text and not alt_text.startswith("Picture"):
                    content_lines.append(f"[IMAGE: {alt_text}]")
                else:
                    content_lines.append("[IMAGE: no alt text]")

        content_str = "\n".join(content_lines)
        
        # 3. Speaker Notes
        notes_str = ""
        has_notes = False
        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()
            if notes_text:
                has_notes = True
                notes_str = notes_text

        # 4. Process Chunks
        full_content = f"{title_prefix}[CONTENT]\n{content_str}\n"
        if has_notes:
            full_content += f"[NOTES]\n{notes_str}\n"

        token_count = get_token_count(full_content)
        
        metadata = {
            'slide_number': slide_number,
            'slide_title': slide_title,
            'has_notes': has_notes,
            'has_images': has_images,
            'chunk_type': 'slide'
        }

        if token_count <= 600:
            chunks.append({
                'content': full_content,
                'token_count': token_count,
                'chunk_metadata': metadata
            })
        else:
            # Split into two chunks: Title + Content, and Title + Notes
            # First Chunk: Content
            chunk1_text = f"{title_prefix}[CONTENT]\n{content_str}\n"
            chunks.append({
                'content': chunk1_text,
                'token_count': get_token_count(chunk1_text),
                'chunk_metadata': metadata
            })
            
            # Second Chunk: Notes
            if has_notes:
                chunk2_text = f"{title_prefix}[NOTES]\n{notes_str}\n"
                chunks.append({
                    'content': chunk2_text,
                    'token_count': get_token_count(chunk2_text),
                    'chunk_metadata': metadata
                })

    return chunks

if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold yellow]Usage:[/bold yellow] python src/parsers/pptx_parser.py <path_to_pptx>")
    else:
        file_path = sys.argv[1]
        results = parse_pptx(file_path)
        
        console.print(f"\n[bold green]Parsed {len(results)} chunks from {len(results)} slides (or split slides) in:[/bold green] {file_path}")
        
        for i, chunk in enumerate(results[:2]):
            console.print(f"\n[bold cyan]--- Chunk {i} ---[/bold cyan]")
            console.print(f"[bold]Metadata:[/bold] {chunk['chunk_metadata']}")
            console.print(f"[bold]Tokens:[/bold] {chunk['token_count']}")
            console.print(f"[bold]Content Preview:[/bold]\n{chunk['content'][:300]}...")
