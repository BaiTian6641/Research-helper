"""Ollama HTTP wrapper — LLM client for local inference."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around the Ollama HTTP API."""

    def __init__(
        self,
        model: str = "qwen3.5-reasoning",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def health_check(self) -> bool:
        """Check if Ollama is running and responsive."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return names of models installed in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a prompt and return the text response."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

    async def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict | list:
        """Send a prompt with JSON format enforcement and return parsed JSON."""
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            raw_text = resp.json().get("response", "{}")

        # Parse JSON — handle common issues
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
            if match:
                return json.loads(match.group(1).strip())
            # Try to find first { or [ and parse from there
            for start_char, end_char in [("{", "}"), ("[", "]")]:
                start_idx = raw_text.find(start_char)
                end_idx = raw_text.rfind(end_char)
                if start_idx != -1 and end_idx != -1:
                    return json.loads(raw_text[start_idx : end_idx + 1])
            logger.error("Failed to parse LLM JSON response: %s", raw_text[:200])
            return {}

    async def is_model_available(self) -> bool:
        """Check if the configured model is installed."""
        models = await self.list_models()
        return any(self.model in m for m in models)
