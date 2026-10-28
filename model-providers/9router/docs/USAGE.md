# 9router - mechanism reference

The backend registers a ProviderProfile for `http://localhost:20128/v1`.
`NINEROUTER_API_KEY` is preferred, with `NINEROUTER_KEY` supported as an alias.
Discovery sends Bearer auth when set, limits replies to 1 MiB and accepts only
valid unique string IDs from the live `data` list. Combos are ordinary IDs.
An empty live catalog stays empty. No invented wildcard IDs are added.

Discovery refreshes after 60 seconds when called again. Hermes may separately
cache the provider's registration snapshot until refresh/restart. If discovery fails, the provider exposes an empty list until a valid live catalog is available.
The plugin does not manage gateway quotas, account rotation or native endpoint
selection. Current 9Router separately supports `/v1/chat/completions` and
`/v1/messages`; a shared `/v1` prefix does not make their schemas equivalent.

Manifest base_url metadata is informational; the code constant is the target.
The plugin publishes its native `model-picker` skill where supported. No live
laptop gateway or real provider was called to verify this candidate.
