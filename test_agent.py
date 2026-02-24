import requests
import json

BASE_URL = "http://localhost:8000"

def test_agent():
    print("Testing /generate/agent (Agentic Loop)...")
    
    payload = {
        "question": "Write a python function to check if a number is prime. purposely make a small syntax error like a missing colon so we can see the self-correction loop in action.",
        "language": "python"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/generate/agent", json=payload, timeout=300)
        resp.raise_for_status()
        result = resp.json()
        
        print("\nAgent Result:")
        print(f"Iteration Count: {result['iteration_count']}")
        print(f"Is Incomplete: {result['is_incomplete']}")
        print(f"Errors Found: {result['errors']}")
        print("\nGenerated Code:")
        print("-" * 40)
        print(result['generated_code'])
        print("-" * 40)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_agent()
