# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Validate tool name, argument object and specific file path first. A requested read does not grant edit eligibility: only post_tool_call status=ok (native Hermes) or success (legacy) records it. Failed or blocked reads do not satisfy read-before-edit.

Tested in isolated development fixtures. This is not proof of the installed laptop source/runtime or a deployment.
