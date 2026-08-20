from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OllamaGeneration:
    model: str
    response: str
    latency_ms: float


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def list_models(self) -> List[str]:
        payload = self._get_json("/api/tags")
        return [model["name"] for model in payload.get("models", []) if "name" in model]

    def choose_model(self, requested_model: Optional[str] = None) -> str:
        if requested_model:
            return requested_model
        models = self.list_models()
        if not models:
            raise OllamaUnavailable(
                "Ollama is reachable, but no local models are installed. Run `ollama pull <model>` yourself before AI benchmarks."
            )
        return models[0]

    def generate(self, prompt: str, model: str, temperature: float = 0.0) -> OllamaGeneration:
        request_payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        started = time.perf_counter()
        payload = self._post_json("/api/generate", request_payload)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return OllamaGeneration(
            model=model,
            response=str(payload.get("response", "")),
            latency_ms=elapsed_ms,
        )

    def embed(self, text: str, model: str) -> List[float]:
        payload = self._post_json("/api/embed", {"model": model, "input": text})
        embeddings = payload.get("embeddings")
        if not embeddings:
            raise OllamaUnavailable(f"Ollama embedding response missing 'embeddings' for model {model}")
        return [float(value) for value in embeddings[0]]

    def _get_json(self, path: str) -> Dict[str, object]:
        request = Request(f"{self.base_url}{path}", method="GET")
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise OllamaUnavailable(
                "Ollama is not reachable at http://127.0.0.1:11434. Start the Ollama app or run `ollama serve`."
            ) from exc

    def _post_json(self, path: str, payload: Dict[str, object]) -> Dict[str, object]:
        encoded = json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            raise OllamaUnavailable(
                "Ollama stopped responding during generation. Check the local Ollama server and model."
            ) from exc
