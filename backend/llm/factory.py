"""
Returns the configured LLM provider based on the LLM_PROVIDER env var.
This is the only place that needs to change to add a new provider.
"""

import os

from .base import LLMProvider
from .claude_provider import ClaudeProvider


def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "claude").lower()
    if provider == "claude":
        return ClaudeProvider()
    raise ValueError(f"unknown LLM_PROVIDER: {provider}")