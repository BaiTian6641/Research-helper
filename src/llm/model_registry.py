"""Model registry — available Ollama models + capability tags."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    name: str
    display_name: str
    size_gb: float
    vram_gb: int
    best_for: str
    is_default: bool = False


# Ordered by preference (first = recommended)
MODELS: list[ModelInfo] = [
    ModelInfo(
        name="qwen3.5-reasoning",
        display_name="Qwen3.5-27B-Claude-Opus-Reasoning-Distilled (★ Recommended)",
        size_gb=17.0,
        vram_gb=20,
        best_for="Deep reasoning, gap analysis, narrative summary",
        is_default=True,
    ),
    ModelInfo(
        name="qwq:32b",
        display_name="QwQ 32B",
        size_gb=20.0,
        vram_gb=24,
        best_for="Chain-of-thought reasoning",
    ),
    ModelInfo(
        name="deepseek-r1:14b",
        display_name="DeepSeek-R1 14B",
        size_gb=9.0,
        vram_gb=10,
        best_for="Reasoning / gap analysis (lighter)",
    ),
    ModelInfo(
        name="deepseek-r1:32b",
        display_name="DeepSeek-R1 32B",
        size_gb=20.0,
        vram_gb=24,
        best_for="Deep reasoning, proposal critique",
    ),
    ModelInfo(
        name="qwen2.5:14b",
        display_name="Qwen 2.5 14B",
        size_gb=9.0,
        vram_gb=10,
        best_for="Balanced reasoning + speed",
    ),
    ModelInfo(
        name="qwen2.5:32b",
        display_name="Qwen 2.5 32B",
        size_gb=20.0,
        vram_gb=24,
        best_for="Highest quality analysis",
    ),
    ModelInfo(
        name="mistral:7b",
        display_name="Mistral 7B",
        size_gb=4.1,
        vram_gb=6,
        best_for="Fast summaries, low VRAM / CPU fallback",
    ),
    ModelInfo(
        name="phi4:14b",
        display_name="Phi-4 14B",
        size_gb=9.0,
        vram_gb=10,
        best_for="Structured JSON extraction",
    ),
]

# Fallback order
FALLBACK_ORDER = [
    "qwen3.5-reasoning",
    "qwq:32b",
    "deepseek-r1:14b",
    "qwen2.5:14b",
    "mistral:7b",
]


def get_default() -> str:
    """Return the default model name."""
    return "qwen3.5-reasoning"


def get_model_info(name: str) -> ModelInfo | None:
    for m in MODELS:
        if m.name == name:
            return m
    return None


def get_all_models() -> list[ModelInfo]:
    return MODELS.copy()


async def find_best_available(installed: list[str]) -> str | None:
    """Given list of installed model names, return best match from fallback order."""
    installed_lower = {m.lower() for m in installed}
    for candidate in FALLBACK_ORDER:
        if any(candidate in m for m in installed_lower):
            return candidate
    return None
