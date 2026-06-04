import requests
import json
from typing import Generator
from backend.core.config import settings


class LLMError(Exception):
    """Raised when an LLM provider is unavailable or returns an error."""


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
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=120
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.ConnectionError:
            raise LLMError(
                f"Ollama is not reachable at {self.base_url}. "
                "Make sure Ollama is running and the OLLAMA_BASE_URL is correct."
            )
        except requests.Timeout:
            raise LLMError("Ollama request timed out. The model may be overloaded.")
        except requests.RequestException as e:
            raise LLMError(f"Ollama returned an error: {e}")

    def generate_stream(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
        }
        try:
            with requests.post(
                f"{self.base_url}/api/generate", json=payload, stream=True, timeout=120
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        yield json.loads(line).get("response", "")
        except requests.RequestException as e:
            raise LLMError(f"Ollama streaming error: {e}")


from huggingface_hub import InferenceClient


class HuggingFaceLLM(LLMProvider):
    def __init__(self):
        model_id = settings.HF_INFERENCE_API_URL
        if "models/" in model_id:
            model_id = model_id.split("models/")[-1]
        self.client = InferenceClient(token=settings.HF_TOKEN)
        self.model = model_id

    def _format_prompt(self, prompt: str, system_prompt: str = "") -> str:
        if system_prompt:
            return f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt} [/INST]"
        return f"<s>[INST] {prompt} [/INST]"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=512,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception:
            # Fall back to text_generation for models that don't support chat endpoint
            try:
                return self.client.text_generation(
                    self._format_prompt(prompt, system_prompt),
                    model=self.model,
                    max_new_tokens=512,
                    temperature=0.3,
                    return_full_text=False,
                )
            except Exception as e:
                raise LLMError(f"Hugging Face API error: {repr(e)}")

    def generate_stream(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt)


class GroqLLM(LLMProvider):
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            response = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "max_tokens": 512, "temperature": 0.3},
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.ConnectionError:
            raise LLMError("Groq API is not reachable. Check your network connection.")
        except requests.HTTPError as e:
            raise LLMError(f"Groq API error: {e.response.status_code} {e.response.text}")
        except requests.RequestException as e:
            raise LLMError(f"Groq request failed: {e}")

    def generate_stream(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt)


def get_llm() -> LLMProvider:
    if settings.LLM_PROVIDER == "groq":
        return GroqLLM()
    if settings.LLM_PROVIDER == "hf":
        return HuggingFaceLLM()
    return OllamaLLM()
