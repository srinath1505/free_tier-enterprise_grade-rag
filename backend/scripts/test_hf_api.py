import sys
import os
import requests
# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

from huggingface_hub import InferenceClient

def test_hf_api():
    print("--- Testing Hugging Face Inference API (via Client) ---")
    
    token = settings.HF_TOKEN
    model = settings.HF_INFERENCE_API_URL # This is now the Model ID
    
    if not token:
        print("ERROR: HF_TOKEN is missing in .env configuration.")
        return

    print(f"Target Model: {model}")
    print(f"Token: {token[:4]}...{token[-4:]} (Masked)")

    client = InferenceClient(token=token)
    
    try:
        response = client.text_generation(
            prompt="Hello, are you working?",
            model=model,
            max_new_tokens=20
        )
        print("SUCCESS! API responded.")
        print("Response:", response)

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_hf_api()
