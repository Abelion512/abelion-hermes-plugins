# Ordered validation

Input -> type/shape -> requirement/value -> effect -> confirmed outcome. A failed branch stops before the corresponding effect; it is not a successful operation.

Lease requests reject malformed JSON, unknown fields, non-boolean `force`, and `force` on acquire with HTTP 422 before upstream RPC. Only an explicit boolean `true` on release may request forced release. Existing auth and viewer-capability checks remain.

WebSocket upgrades use the canonical Hermes auth function. If the module/function is missing or the auth function throws, the upgrade is denied. The upstream override is ignored outside explicit test mode; test mode rejects non-loopback hosts and non-`ws` schemes. Frames are bounded to 16 MiB before upstream forwarding.

Verified in isolated fixtures, including absent/raising-auth and test-override boundary cases. This is not proof of an installed laptop runtime or deployment. See the current repository CI run for the exact tested commit; evidence applies only to the exercised paths.
