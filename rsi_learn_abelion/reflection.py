import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Global cache to store messages between post_llm_call and on_session_end
_session_messages = {}

# Local research path for isolation
PROJECT_ROOT = Path("/media/abelion/Isaf/ican/project/references/hermes-agent")
RESEARCH_DATA_DIR = PROJECT_ROOT / "docs/abelion/reflections"

REFLECTION_PROMPT = """
Analyze the conversation history above. Your goal is to extract "Experience" data for a Recursive Self-Improvement (RSI) loop.

Provide a JSON object with the following fields:
1. "summary": A 1-sentence summary of the task.
2. "status": "success", "failure", or "partial".
3. "errors": List of specific technical errors encountered (if any).
4. "lessons": List of specific procedural lessons for the agent to follow next time to be more efficient or avoid the same errors.
5. "recommendations": Suggestions for improving the agent's system prompt or skills.

Respond ONLY with the JSON object.
"""


def cache_messages(session_id=None, conversation_history=None, **kwargs):
    """
    Hook: post_llm_call
    """
    if session_id and conversation_history:
        _session_messages[session_id] = conversation_history
        logger.debug(f"[abelion_autonomous] Cached messages for session {session_id}")


def record_reflection(ctx, session_id=None, **kwargs):
    """
    Active reflection recorder for Phase 1.1.
    Hook: on_session_end
    """
    if not session_id:
        return

    messages = _session_messages.get(session_id, [])
    if not messages:
        messages = kwargs.get("messages", [])

    if not messages:
        return

    history_text = ""
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join([
                p.get("text", "") for p in content if p.get("type") == "text"
            ])
        history_text += f"{role.upper()}: {content}\n\n"

    try:
        # Use ctx.llm facade
        result = ctx.llm.complete(
            messages=[
                {
                    "role": "user",
                    "content": f"CONVERSATION HISTORY:\n\n{history_text}\n\n{REFLECTION_PROMPT}",
                }
            ],
            purpose="self_reflection",
        )

        reflection_data = {}
        try:
            text = result.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            reflection_data = json.loads(text)
        except Exception:
            reflection_data = {"raw_text": result.text}

        # Save to local research directory
        os.makedirs(RESEARCH_DATA_DIR, exist_ok=True)

        final_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "model_used": result.model,
            "provider": result.provider,
            "reflection": reflection_data,
            "metadata": {
                k: str(v) for k, v in kwargs.items() if k not in ["messages", "ctx"]
            },
        }

        filename = f"reflection_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{session_id[:8]}.json"
        filepath = RESEARCH_DATA_DIR / filename

        with open(filepath, "w") as f:
            json.dump(final_record, f, indent=2)
        logger.info(f"[abelion_autonomous] Recorded isolated reflection: {filepath}")

    except Exception as e:
        logger.error(f"[abelion_autonomous] Active reflection failed: {e}")
        _record_passive(session_id, kwargs)


def _record_passive(session_id, kwargs):
    os.makedirs(RESEARCH_DATA_DIR, exist_ok=True)
    reflection = {
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "event": "session_end_passive_fallback",
        "metadata": {k: str(v) for k, v in kwargs.items() if k != "messages"},
    }
    filename = f"reflection_passive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{session_id[:8]}.json"
    filepath = RESEARCH_DATA_DIR / filename
    try:
        with open(filepath, "w") as f:
            json.dump(reflection, f, indent=2)
    except Exception:
        pass
