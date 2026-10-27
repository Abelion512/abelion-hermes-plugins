# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Lease requests reject malformed JSON, unknown fields, non-boolean force and force on acquire with HTTP422 before upstream RPC. Only an explicit boolean true on release may request forced release. Existing auth and viewer capability checks remain.

Tested in isolated development fixtures. This is not proof of the installed laptop source/runtime or a deployment.
