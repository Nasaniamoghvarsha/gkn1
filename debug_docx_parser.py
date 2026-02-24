from src.parsers.docx_parser import parse_docx
import json

def debug_docx():
    file_path = "tests/fixtures/sample.docx"
    chunks = parse_docx(file_path)
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i}:")
        print(f"  Metadata: {chunk['chunk_metadata']}")
        print(f"  Content: {chunk['content'][:50]}...")

if __name__ == "__main__":
    debug_docx()
