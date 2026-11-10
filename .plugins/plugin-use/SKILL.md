---
name: plugin-use
description: Install, verify, use, disable, and roll back plugins here.
version: 0.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [plugin, use, install, verify, disable, rollback, monorepo]
---

# Plugin Use Skill

This repo is a source monorepo for standalone Hermes Agent plugins. A plugin folder is not the same thing as a plugin installed in a running Hermes home. Use this skill when you need to install, enable, verify, understand, disable, or roll back a plugin that lives in this repo.

Use this when the user asks how to try a plugin, how to verify one, or how to remove one without mangling a running profile.

## When to Use

- Installing a plugin from this monorepo into a Hermes home.
- Verifying that a plugin is enabled and discovered.
- Reading the right doc layer for a plugin question.
- Disabling or removing a plugin safely.
- Understanding what a merge or local change does and does not do.

Do not use this skill as a substitute for the plugin's own README and `docs/` when the question is plugin-specific. Do not use it to justify upgrading a daily profile based only on repo tests.

## How to Apply

1. Decide which plugin and which environment.
   - Identify the plugin by its monorepo public ID and folder, not just by a short nickname.
   - Decide whether you are working on a disposable test profile or a real daily profile. Repo tests do not prove a laptop or daily profile is safe to enable.

2. Read the plugin's doc trio first.
   - `README.md` for quickstart, install, verify, disable/rollback, and honest limits.
   - `docs/USAGE.md` for the mechanism: hooks, middleware, skills, state, config, limits.
   - `docs/VALIDATION.md` for what the test layers prove and what they do not.

3. If the plugin bundles a skill, remember that the skill is the agent-facing guidance only while the plugin is enabled and the host supports `ctx.register_skill`. The README alone is not automatic discovery.

4. Install from this monorepo through the supported path for the plugin:
   - Many plugins publish `install.sh` from a clone.
   - The repo ships `update-plugins.sh` to sync active plugin folders into a Hermes plugin directory for the plugins it tracks.
   - Use the plugin's documented install path, not an improvised copy.

5. Verify with the plugin's documented checks:
   - `hermes plugins list`
   - `hermes plugins doctor <plugin>` or the plugin's own doctor command when documented
   - Confirm the plugin appears enabled and the expected skill/hook/tab is advertised only if the host supports it

6. When trying a plugin, prefer a disposable profile:
   - Stop the relevant Hermes process first if you are touching a running profile.
   - Back up config and plugin versions before changing them.
   - Start a new session after loading or unloading the plugin.
   - Do not delete plugin directories from a live profile just because a test run used a throwaway one.

7. Disable or roll back using the plugin's documented path:
   - Disable through Hermes plugin management when that is the supported path.
   - Remove through the documented removal path when you want it gone.
   - Restore a known backup rather than improvising a partial revert.
   - If mandatory/required mode is involved, do not leave required mode true while removing the plugin that owns the required contract; that is intended to deny.

8. Treat repo merges as source changes, not as automatic installed-profile migration:
   - A merge does not migrate an installed profile, change privacy settings, or remove old installed plugins by itself.
   - An old installed copy is separate state and does not disappear just because the repo folder was removed.

## Pitfalls

- Assuming a plugin is safe for daily use because its unit tests pass.
- Editing a running profile without stopping the process or backing up first.
- Removing a required plugin while required mode is still true.
- Confusing "plugin folder exists in the repo" with "plugin is installed and enabled."
- Relying on a skill that is not registered on the current host.
- Using the repo's install sync as if it were a full profile migration.

## Verification

- The plugin is discoverable/enabled in the target environment according to its own docs.
- The doc layer you read matches the behavior you are relying on.
- Any install, enable, disable, or removal path you used is the one the plugin documents.
- If you changed a running profile, you stopped the process first and kept a backup.

## Wrong requirement or value

If you cannot tell whether the target is a disposable test profile or a daily profile, stop and ask before mutating anything. If a plugin's required host or required core contract is not present, do not claim the plugin gives the same guarantee. If you are asked to remove a plugin but required mode depends on it, say so before proceeding.
