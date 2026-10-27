# Rollback source, not active plugins

The archive preserves retired Shield, tool-context, RSI code and the previous cross-plugin integration test file from the tested six-plugin candidate. SHA256SUMS records integrity. It is not extracted under plugins and is not an install target. The previous complete six-plugin worktree is also preserved separately during local review.

No installed RSI_LESSONS.md, JSONL metrics or user profile was read, changed, moved or deleted. This is source cleanup, not user-data migration.

For a reviewed disposable rollback, stop the process, restore pinned plugin/config snapshots together, then restart with a new session. Do not extract this archive into a live profile or assume restoration of source alone restores installed selection/settings. Required privacy must retain its matching core and owner. No automatic rollback script is provided.
