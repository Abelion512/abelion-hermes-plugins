# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Model discovery bounds response size, requires an object/list payload and nonempty string IDs with the supported identifier alphabet. Invalid IDs are excluded, duplicates removed; malformed/unavailable responses retain the existing curated fallback, not proof of live availability.

Tested in isolated development fixtures. This is not proof of the installed laptop source/runtime or a deployment.
