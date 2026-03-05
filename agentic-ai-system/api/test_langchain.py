import httpx
import json

def test():
    try:
        response = httpx.post(
            "http://127.0.0.1:8000/v1/langchain/agent/run",
            json={"task": "What is 42 * 18 + 99?", "max_iterations": 5},
            timeout=60.0,
        )
        print(response.status_code)
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
