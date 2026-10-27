"""9Router model provider plugin.

Mendaftarkan 9Router sebagai provider di Hermes dengan daftar model lengkap
dari endpoint lokal ``http://localhost:20128/v1/models``.

Dengan ini, ``/model`` picker di CLI/gateway akan menampilkan semua model
9Router sebagai opsi yang bisa dipilih tanpa harus inject manual di config.
"""

from __future__ import annotations

import json
import logging
import os
import time
import re
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SLUG = "9router"
LABEL = "9Router"
DESCRIPTION = "9Router multi-model gateway (localhost:20128)"
BASE_URL = "http://localhost:20128/v1"

# Static curated list. Fallback saat /v1/models unreachable.
# Includes oc/* and mmf/* — models that 9Router routes even though
# they don't appear in /v1/models listing. Add more variants here
# if 9Router gains new route prefixes.
_CURATED: list[str] = [
    # ── oc/* — OpenCode variants routed via 9Router ────────
    "oc/nemotron-3-ultra-free",
    "oc/deepseek-v4-flash",
    "oc/deepseek-v4-flash-free",
    "oc/deepseek-v4-pro",
    "oc/claude-sonnet-5",
    "oc/claude-haiku-4.5",
    "oc/gemini-3.1-flash-lite",
    "oc/gpt-5.4-mini",
    "oc/mimo-v2.5-free",

    # ── mmf/* — MMF variants routed via 9Router ────────────
    "mmf/qwen3-32b",
    "mmf/glm-5.2",
    "mmf/minimax-m3",
    "mmf/kimi-k2.6",
    "mmf/nemotron-3-ultra",
    "mmf/deepseek-v4-flash",
    "mmf/mimo-auto",

    # ── ag/ — Anthropic/Gemini via 9Router ─────────────────
    "ag/claude-opus-4-6-thinking",
    "ag/claude-sonnet-4-6",
    "ag/gemini-3.1-pro-low",
    "ag/gemini-3.5-flash-extra-low",
    "ag/gemini-3.5-flash-low",
    "ag/gemini-3-flash",
    "ag/gemini-3-flash-agent",
    "ag/gemini-pro-agent",
    "ag/gpt-oss-120b-medium",
    "cl/anthropic/claude-opus-4.6",
    "cl/anthropic/claude-opus-4.7",
    "cl/anthropic/claude-sonnet-4.6",
    "cl/google/gemini-3.1-flash-lite-preview",
    "cl/google/gemini-3.1-pro-preview",
    "cl/kwaipilot/kat-coder-pro",
    "cl/openai/gpt-5.3-codex",
    "cl/openai/gpt-5.4",
    "cx/gpt-5.3-codex",
    "cx/gpt-5.3-codex-high",
    "cx/gpt-5.3-codex-high-review",
    "cx/gpt-5.3-codex-low",
    "cx/gpt-5.3-codex-low-review",
    "cx/gpt-5.3-codex-none",
    "cx/gpt-5.3-codex-none-review",
    "cx/gpt-5.3-codex-review",
    "cx/gpt-5.3-codex-spark",
    "cx/gpt-5.3-codex-spark-review",
    "cx/gpt-5.3-codex-xhigh",
    "cx/gpt-5.3-codex-xhigh-review",
    "cx/gpt-5.4",
    "cx/gpt-5.4-mini",
    "cx/gpt-5.4-mini-review",
    "cx/gpt-5.4-review",
    "cx/gpt-5.5",
    "cx/gpt-5.5-review",
    "gc/gemini-2.5-flash",
    "gc/gemini-2.5-flash-lite",
    "gc/gemini-2.5-pro",
    "gc/gemini-3.1-flash-lite",
    "gc/gemini-3.1-flash-lite-preview",
    "gemini/gemini-3.1-flash-lite-preview",
    "gemini/gemini-3.1-pro-preview",
    "gemini/gemini-3-flash-preview",
    "gemini/gemma-4-31b-it",
    "groq/llama-3.3-70b-versatile",
    "groq/meta-llama/llama-4-maverick-17b-128e-instruct",
    "groq/openai/gpt-oss-120b",
    "groq/qwen/qwen3-32b",
    "kc/nvidia/nemotron-3-super-120b-a12b:free",
    "kc/openrouter/free",
    "kr/claude-haiku-4.5",
    "kr/claude-sonnet-4.5",
    "kr/claude-sonnet-4.5-agentic",
    "kr/claude-sonnet-4.5-thinking",
    "kr/claude-sonnet-4.5-thinking-agentic",
    "kr/claude-sonnet-5",
    "kr/claude-sonnet-5-agentic",
    "kr/claude-sonnet-5-thinking",
    "kr/claude-sonnet-5-thinking-agentic",
    "kr/deepseek-3.2",
    "kr/glm-5",
    "kr/MiniMax-M2.5",
    "kr/qwen3-coder-next",
    "nvidia/deepseek-ai/deepseek-v4-flash",
    "nvidia/deepseek-ai/deepseek-v4-pro",
    "nvidia/minimaxai/minimax-m2.7",
    "nvidia/minimaxai/minimax-m3",
    "nvidia/moonshotai/kimi-k2.6",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/z-ai/glm-5.2",
    "ollama/minimax-m3",
    "ollama/minimax-m3:cloud",
    "ollama/nemotron-3-super:latest",
    "ollama/nemotron-3-ultra:cloud",
    "openrouter/cohere/north-mini-code:free",
    "openrouter/google/gemma-4-26b-a4b-it:free",
    "openrouter/google/gemma-4-31b-it:free",
    "openrouter/nvidia/nemotron-3-nano-30b-a3b:free",
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/openrouter/free",
    "openrouter/poolside/laguna-m.1:free",
    "openrouter/poolside/laguna-xs.2:free",
]

# Cache
_discovered: list[str] | None = None
_discovered_at = 0.0
_CACHE_SECONDS = 60.0


def _fetch_models(timeout: float = 5.0) -> list[str] | None:
    """Fetch model list from 9Router /v1/models."""
    try:
        headers = {"Accept": "application/json"}
        key = os.environ.get("NINEROUTER_API_KEY") or os.environ.get("NINEROUTER_KEY")
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(f"{BASE_URL}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw=resp.read(1_048_577)
            if len(raw)>1_048_576:return None
            payload = json.loads(raw.decode())
        if not isinstance(payload,dict):return None
        items = payload.get("data")
        if isinstance(items, list):
            ids = list(dict.fromkeys(m["id"] for m in items
                if isinstance(m,dict) and isinstance(m.get("id"),str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}",m["id"])))
            return ids if ids or not items else None
    except Exception as exc:
        logger.debug("[9router] /v1/models fetch failed: %s", exc)
    return None


def get_available_models() -> list[str]:
    """Use the validated live catalog; offline curated entries are unverified fallback."""
    global _discovered, _discovered_at
    now = time.monotonic()
    if _discovered is None or now - _discovered_at >= _CACHE_SECONDS:
        live = _fetch_models()
        if live is not None:
            _discovered = live
        else:
            logger.warning("[9router] Live catalog unavailable; curated fallback is unverified")
            _discovered = list(_CURATED)
        _discovered_at = now
    return list(_discovered)


# ── Self-register at import time ───────────────────────────────────────
# Hermes calls ``from providers import register_provider; register_provider(p)``
# implicitly by importing this module.
try:
    from providers.base import ProviderProfile

    profile = ProviderProfile(
        name=SLUG,
        display_name=LABEL,
        description=DESCRIPTION,
        base_url=BASE_URL,
        models_url=BASE_URL + "/models",
        fallback_models=tuple(get_available_models()),
        auth_type="api_key",
        env_vars=("NINEROUTER_API_KEY", "NINEROUTER_KEY"),
    )
    from providers import register_provider

    register_provider(profile)
    logger.info("[9router] Registered as provider with %d models", len(get_available_models()))
except Exception as exc:
    logger.warning("[9router] Failed to register: %s", exc)



# ── Bundled agent skills ─────────────────────────────────────────────
# The provider profile above self-registers at import time; register(ctx)
# only publishes skills/*/SKILL.md (guarded for hosts without register_skill).

_SKILL_DESCRIPTIONS = {
    "model-picker": "Pick and use 9Router provider models in Hermes.",
}


def register(ctx):
    register_skill = getattr(ctx, "register_skill", None)
    if register_skill is None:
        logger.info("[9router] host has no ctx.register_skill; bundled skills skipped")
        return
    skills_dir = Path(__file__).resolve().parent / "skills"
    if not skills_dir.is_dir():
        return
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.is_file():
            register_skill(
                name=child.name,
                path=skill_md,
                description=_SKILL_DESCRIPTIONS.get(child.name, ""),
            )
