import requests
import json
from typing import List, Dict, Generator
from backend.core.config import settings

class LLMProvider:
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_stream(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        raise NotImplementedError

class OllamaLLM(LLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        # Simple non-streaming implementation
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False
        }
        try:
            response = requests.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.RequestException as e:
            return f"Error communicating with Ollama: {e}"

    def generate_stream(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True
        }
        try:
            with requests.post(f"{self.base_url}/api/generate", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        yield data.get("response", "")
        except requests.RequestException as e:
            yield f"Error: {e}"

from huggingface_hub import InferenceClient

class HuggingFaceLLM(LLMProvider):
    def __init__(self):
        # We pass the token and model explicitly
        # config.HF_INFERENCE_API_URL should now just be the model ID or we parse it
        # Let's assume config has the Model ID now, or we extract it.
        # But to be safe, let's update config to just hold the Model ID.
        model_id = settings.HF_INFERENCE_API_URL.split("models/")[-1] 
        # Check if URL was passed, fallback to hardcoded reliable model if needed
        if "http" in settings.HF_INFERENCE_API_URL:
             # Just in case user still has full URL
             pass
        else:
             model_id = settings.HF_INFERENCE_API_URL
             
        self.client = InferenceClient(token=settings.HF_TOKEN)
        self.model = model_id

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # Use Chat Completion API (Universal for Instruction Models)
            response = self.client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=512,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"HF API Error Details: {repr(e)}")
            return f"Error communicating with HF API: {repr(e)}"

    def generate_stream(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        # HF Inference API streaming is different/limited depending on model support
        # For simplicity, we fallback to non-streaming for now or implement if needed
        yield self.generate(prompt, system_prompt)

def get_llm() -> LLMProvider:
    if settings.LLM_PROVIDER == "hf":
        return HuggingFaceLLM()
    return OllamaLLM()
