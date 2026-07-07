"""pii_mask_abelion — llm_request middleware: PII masking."""

from __future__ import annotations
import logging
from .pii_middleware import pii_middleware

logger = logging.getLogger(__name__)

def register(ctx):
    ctx.register_middleware("llm_request", pii_middleware)
    logger.info("[pii_mask_abelion] PII masking middleware registered")
