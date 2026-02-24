import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_api():
    # 1. Health
    print("Testing /health...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"Health: {resp.json()}")

    # 2. Ingest
    print("\nTesting /ingest...")
    file_path = "tests/fixtures/sample.docx"
    with open(file_path, "rb") as f:
        resp = requests.post(f"{BASE_URL}/ingest", files={"file": f})
    print(f"Ingest Result: {resp.json()}")

    # 3. Query
    print("\nTesting /query...")
    query_data = {
        "question": "What is the security protocol for GKN Aerospace?",
        "file_type_filter": ".docx"
    }
    resp = requests.post(f"{BASE_URL}/query", json=query_data)
    print(f"Query Result: {json.dumps(resp.json(), indent=2)}")

    # 4. Stream Query
    print("\nTesting /query/stream...")
    resp = requests.post(f"{BASE_URL}/query/stream", json=query_data, stream=True)
    print("Stream Response: ", end="", flush=True)
    for chunk in resp.iter_content(decode_unicode=True):
        print(chunk, end="", flush=True)
    print("\n")

if __name__ == "__main__":
    test_api()
