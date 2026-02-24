import sys
import os
from typing import List, Dict, Any
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken
from rich.console import Console

console = Console()

def get_token_count(text: str, encoding_name: str = "cl100k_base") -> int:
    """Calculates token count for a string using tiktoken."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))

def parse_docx(file_path: str) -> List[Dict[str, Any]]:
    """Parses a .docx file, preserving heading hierarchy and processing tables."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        return []

    doc = DocxDocument(file_path)
    chunks = []
    
    # Text splitter config
    tokenizer = tiktoken.get_encoding("cl100k_base")
    def length_function(text: str) -> int:
        return len(tokenizer.encode(text))

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=400,
        chunk_overlap=80
    )

    current_heading_path = []
    chunk_index = 0

    def add_to_chunks(content: str, chunk_type: str, heading_path: List[str]):
        nonlocal chunk_index
        if not content.strip():
            return
            
        heading_path_str = " > ".join(heading_path)
        sub_chunks = splitter.split_text(content)
        
        for sub_chunk in sub_chunks:
            chunks.append({
                'content': sub_chunk,
                'token_count': get_token_count(sub_chunk),
                'chunk_metadata': {
                    'heading_path': heading_path_str,
                    'chunk_type': chunk_type,
                    'chunk_index': chunk_index
                }
            })
            chunk_index += 1

    # Process paragraphs and tables in order
    for element in doc.element.body:
        if element.tag.endswith('p'):
            # It's a paragraph
            # Find the paragraph object in doc.paragraphs that matches this element
            # Actually, it's easier to iterate through all body elements
            pass

    # A better way to iterate elements in order is to use the internal xml or a helper
    # However, doc.paragraphs and doc.tables don't give interleaved order easily.
    # We will use the approach of iterating through all children of the body.
    
    for block in doc.iter_block_items():
        if isinstance(block, DocxDocument().paragraphs[0].__class__): # Paragraph check (hacky but works)
            style = getattr(block.style, 'name', '') if block.style else ''
            text = block.text.strip()
            
            if not text:
                continue

            # Update heading path
            if style.startswith('Heading'):
                try:
                    level = int(style.replace('Heading', '').strip())
                    # Truncate path to level - 1
                    current_heading_path = current_heading_path[:level-1]
                    current_heading_path.append(text)
                except ValueError:
                    # Not a standard Heading 1-9
                    add_to_chunks(text, 'paragraph', current_heading_path)
            else:
                add_to_chunks(text, 'paragraph', current_heading_path)
                
        elif hasattr(block, 'rows'): # Table check
            table_text = []
            header_row = ""
            
            for i, row in enumerate(block.rows):
                row_data = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                row_str = "| " + " | ".join(row_data) + " |"
                
                if i == 0:
                    header_row = row_str
                    table_text.append(row_str)
                else:
                    table_text.append(row_str)

            full_table_content = "\n".join(table_text)
            table_tokens = get_token_count(full_table_content)

            if table_tokens <= 400:
                add_to_chunks(full_table_content, 'table', current_heading_path)
            else:
                # Split row by row, prepending header
                # We reuse add_to_chunks but with specific logic here
                for i in range(1, len(table_text)):
                    row_content = header_row + "\n" + table_text[i]
                    add_to_chunks(row_content, 'table', current_heading_path)

    return chunks

# To iterate in order, we need a helper since python-docx doesn't expose it directly
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.document import Document

# Refined implementation with orders
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def parse_docx_refined(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {file_path}")
        return []

    doc = DocxDocument(file_path)
    chunks = []
    
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=400,
        chunk_overlap=80
    )

    current_heading_path = []
    chunk_index = 0


    def add_to_chunks(content: str, chunk_type: str, heading_path: List[str]):
        nonlocal chunk_index
        if not content.strip():
            return
            
        heading_path_str = " > ".join(heading_path)
        # For paragraphs, we use the splitter. Tables are handled specifically.
        if chunk_type == 'paragraph':
            sub_chunks = splitter.split_text(content)
        else:
            # Tables already handled or small enough
            sub_chunks = [content]
        
        for sub_chunk in sub_chunks:
            chunks.append({
                'content': sub_chunk,
                'token_count': get_token_count(sub_chunk),
                'chunk_metadata': {
                    'heading_path': heading_path_str,
                    'chunk_type': chunk_type,
                    'chunk_index': chunk_index
                }
            })
            chunk_index += 1

    # Order-preserving iteration
    parent_elm = doc.element.body
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            para = Paragraph(child, doc)
            style = getattr(para.style, 'name', '') if para.style else ''
            text = para.text.strip()
            
            if not text:
                continue

            if style.startswith('Heading'):
                try:
                    # Heading level detection (Heading 1, Heading 2, etc.)
                    import re
                    match = re.search(r'\d+', style)
                    if match:
                        level = int(match.group())
                        current_heading_path = current_heading_path[:level-1]
                        current_heading_path.append(text)
                    else:
                        add_to_chunks(text, 'paragraph', current_heading_path)
                except Exception:
                    add_to_chunks(text, 'paragraph', current_heading_path)
            else:
                add_to_chunks(text, 'paragraph', current_heading_path)
                
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            table_rows = []
            header_row = ""
            
            for i, row in enumerate(table.rows):
                row_data = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                row_str = "| " + " | ".join(row_data) + " |"
                
                if i == 0:
                    header_row = row_str
                
                table_rows.append(row_str)

            full_table_content = "\n".join(table_rows)
            table_tokens = get_token_count(full_table_content)

            if table_tokens <= 400:
                add_to_chunks(full_table_content, 'table', current_heading_path)
            else:
                # Split row by row, prepend header
                for i in range(1, len(table_rows)):
                    row_content = header_row + "\n" + table_rows[i]
                    add_to_chunks(row_content, 'table', current_heading_path)

    return chunks

# Set the exported function
parse_docx = parse_docx_refined

if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold yellow]Usage:[/bold yellow] python src/parsers/docx_parser.py <path_to_docx>")
    else:
        file_path = sys.argv[1]
        results = parse_docx(file_path)
        
        console.print(f"\n[bold green]Parsed {len(results)} chunks from:[/bold green] {file_path}")
        
        for i, chunk in enumerate(results[:3]):
            console.print(f"\n[bold cyan]--- Chunk {i} ---[/bold cyan]")
            console.print(f"[bold]Metadata:[/bold] {chunk['chunk_metadata']}")
            console.print(f"[bold]Tokens:[/bold] {chunk['token_count']}")
            console.print(f"[bold]Content Preview:[/bold]\n{chunk['content'][:200]}...")
