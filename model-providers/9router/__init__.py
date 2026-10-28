"""9Router model provider plugin.

Mendaftarkan 9Router sebagai provider di Hermes dengan daftar model lengkap
dari endpoint lokal ``http://127.0.0.1:20128/v1/models``.

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
DESCRIPTION = "9Router multi-model gateway (127.0.0.1:20128)"
BASE_URL = "http://127.0.0.1:20128/v1"

# Catalog is live-only. Do not publish an offline list of unverified model IDs.

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
        # Never route a local API key through an environment HTTP(S) proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
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
    """Return only validated IDs from the live gateway; no synthetic fallback inventory."""
    global _discovered, _discovered_at
    now = time.monotonic()
    if _discovered is None or now - _discovered_at >= _CACHE_SECONDS:
        live = _fetch_models()
        if live is not None:
            _discovered = live
        else:
            logger.warning("[9router] Live catalog unavailable; exposing no model IDs")
            _discovered = []
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
