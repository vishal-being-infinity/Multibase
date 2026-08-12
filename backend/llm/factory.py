"""
Returns LLM providers in fallback priority order based on LLM_PROVIDER_ORDER.
This is the only place that needs to change to add, remove, or reorder providers.
"""

import os

from .base import LLMProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider

PROVIDER_MAP = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
}


# returns providers in priority order, e.g. "claude,gemini" -> [ClaudeProvider(), GeminiProvider()]
def get_llm_providers() -> list[LLMProvider]:
    order = os.getenv("LLM_PROVIDER_ORDER", "claude").split(",")
    providers = []
    for name in order:
        name = name.strip().lower()
        if name not in PROVIDER_MAP:
            raise ValueError(f"unknown provider in LLM_PROVIDER_ORDER: {name}")
        providers.append(PROVIDER_MAP[name]())
    return providers