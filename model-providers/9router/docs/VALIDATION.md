# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Model discovery reads at most 1 MiB from the local `/v1/models` response, requires an object containing a data list, accepts only nonempty string IDs from the supported identifier alphabet, and removes duplicates. Oversized, malformed or unavailable responses yield no advertised IDs. There is no static curated fallback.

The adapter is disabled in this repository's install manifest. Tests use synthetic response bodies and do not contact a live 9Router service. This is not proof of installed-laptop behavior or current live model availability.
