# tool-context-abelion - mechanism reference

The `pre_llm_call` hook returns `{"context": ...}` for a non-empty string
user message after the first turn. Otherwise it returns `None` without effects.
The context contains `datetime.now(timezone.utc)` and asks the model to check
actual tool schemas, required values and account approvals.

A valid explicit `available_tools` list is deduplicated and named. With no valid
inventory, the context says to use the host session tool list. It does not invent
a tool map or confer permission. The bundled `turn-context` skill is registered
through `ctx.register_skill` where supported. No configuration is required.
