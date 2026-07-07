"""output_redact_abelion — transform_llm_output: redact credentials from LLM response."""

from __future__ import annotations
import logging
from .output_redact import redact_output

logger = logging.getLogger(__name__)

def register(ctx):
    ctx.register_hook("transform_llm_output", redact_output)
    logger.info("[output_redact_abelion] Output redaction hook registered")
