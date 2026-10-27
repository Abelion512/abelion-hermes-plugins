# Output handling in Hermes

The registered hook operates on final response text. It requests held delivery, applies its parenthetical credential pattern, then invokes the native redactor. It returns `None` when unchanged or when the mapping guard owns final output. Its own optional hook error handling is not a mandatory privacy boundary.

Use `output-redact-abelion:redacted-output-handling` through native Hermes skill discovery while the plugin is enabled. Skill instructions tell the model how to treat placeholders and denials, not how to reconstruct secrets. Disabled plugins stop advertising this skill; older hosts without registration support skip it.

Do not ask users to paste a credential to prove the detector works. Use a synthetic canary and inspect the exact final text. Test with the mapping guard enabled too: the mapping guard's session token must survive, and credentials must never restore. See [README](../README.md) for setup and rollback.
