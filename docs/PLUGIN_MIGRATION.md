# Existing-profile migration to Nebula

This migration is for profiles that previously installed one or more of:

- `pii_mask_abelion` (renamed to `nebula`)
- `screen` (retired)
- `output-redact-abelion` (consolidated into `nebula`)

Removing source folders from this repository does not remove copies already installed in
`~/.hermes/plugins/`. The updater deliberately stops when it finds these directories.
It does not edit an active profile, disable plugins, or delete user state.

## Migration procedure

Perform this in a maintenance window and use the exact Hermes profile that the gateway
actually loads. Do not assume the default profile path if the gateway uses a custom one.

1. **Stop Hermes.** Stop the gateway and any other process using the target profile.
2. **Identify the active profile and native plugin-management commands.** Use the installed
   Hermes version's help output (for example, `hermes plugins --help`). Do not copy a
   disable/remove command from another Hermes version.
3. **Back up before changing anything.** Back up the active profile configuration, the
   current `nebula` directory if present, and every legacy directory detected by the
   updater. Store the backup outside `~/.hermes/plugins/`. Keep permissions and timestamps.
4. **Disable legacy IDs using Hermes native plugin management.** Disable each detected ID:
   `pii_mask_abelion`, `screen`, and/or `output-redact-abelion`. Do not disable
   `nebula` or turn off required Privacy Guard as a shortcut. Verify the active profile
   has exactly one Privacy Guard owner: `nebula`.
5. **Quarantine disabled directories.** Only after the native manager confirms the IDs are
   disabled, move the corresponding directories outside the plugin discovery directory.
   For example:

   ```bash
   stamp="$(date -u +%Y%m%dT%H%M%SZ)"
   quarantine="$HOME/.hermes/plugin-quarantine/$stamp"
   mkdir -p "$quarantine"
   for id in pii_mask_abelion screen output-redact-abelion; do
     if [ -d "$HOME/.hermes/plugins/$id" ]; then
       mv -- "$HOME/.hermes/plugins/$id" "$quarantine/$id"
     fi
   done
   ```

   This is a reversible move, not deletion. Do not move a directory if Hermes still reports
   that ID as enabled or if the active profile is uncertain.
6. **Run the updater.** From the repository checkout, run `./update-plugins.sh`. It must
   complete without finding legacy directories.
7. **Verify before resuming normal work.** Use the installed Hermes version's native plugin
   listing/doctor commands. Confirm `nebula` is loaded exactly once, required mode still
   points to `nebula`, and no retired ID is enabled. Restart Hermes and begin a new session.
   Run the plugin's disposable-profile E2E checks before treating the migration as proven.

## Rollback

1. Stop Hermes again.
2. Restore the backed-up active profile configuration and previous `nebula` directory.
3. Move quarantined legacy directories back to their original paths.
4. Start Hermes with a fresh session and verify the previous plugin state.

Do not restore only the directories while leaving the new configuration active, or vice
versa. Plugin code and its profile configuration must be restored as one consistent set.

## Automated coverage and limits

`tests/test_update_plugins_migration.sh` creates a temporary fake Hermes home and verifies
that each known legacy directory makes the updater stop before `git pull` or `rsync`.
It also verifies that a clean profile proceeds with the normal sync. This is a shell-level
safety test, not a real Hermes profile migration test. Native disable/list behavior must be
verified against the exact installed Hermes version in a disposable profile.
