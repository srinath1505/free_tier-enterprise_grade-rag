import requests
import json

def test_ollama():
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "phi3:mini",
        "prompt": "Hello, are you working?",
        "stream": False
    }
    
    print(f"Testing Ollama at {url}...")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Success!")
        print(response.json().get("response"))
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Status: {e.response.status_code}")
             print(f"Body: {e.response.text}")

if __name__ == "__main__":
    test_ollama()
