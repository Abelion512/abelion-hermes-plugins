# Hermes Agentic Harness — Adaptasi Anthropic Large-Codebase + Mattpock Engineering

## Sumber dan status

- TERVERIFIKASI (https://www.anthropic.com/research/claude-code-best-practices, HTTP 200) — Explore, plan, code, commit; TDD; screenshot iterate; multi-Claude.
- TERVERIFIKASI (https://claude.com/resources/articles/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start, HTTP 200) — harness 5 lapis: CLAUDE.md, hooks, skills, plugins, MCP; plus LSP dan subagents; navigasi agentic bukan RAG; CLAUDE.md lean + layered.
- TERVERIFIKASI (https://www.anthropic.com/research/building-effective-agents, HTTP 200) — workflow vs agent; Orchestrator-workers; Evaluator-optimizer; tool design.
- TERVERIFIKASI (https://code.claude.com/docs/en/agents, HTTP 200) — subagents vs agent teams vs dynamic workflows vs worktrees.
- Skill lokal: mattpock-engineering (seams, TDD, diagnosing-bugs, tracer bullets, two-axis review).

## Inventaris Hermes saat ini (2026-11-06, TERVERIFIKASI via terminal)

| Lapisan Anthropic | Setara di Hermes ini | Status |
|---|---|---|
| CLAUDE.md | AGENTS.md (portable, cwd-only) / .hermes.md (hierarchical, walks to git root) | AGENTS.md ada; .hermes.md belum ada — ditambahkan oleh adopsi ini |
| Hooks | Shell hooks: pre_llm_call, pre_tool_call, post_tool_call, post_llm_call, pre_approval_request | Aktif, tapi hanya notify_9r.py (working/done/blocked). Belum ada lint/test/self-improving hook — script contoh ditambahkan di docs/hooks-examples/ |
| Skills | Hermes skills (progressive disclosure, auto-load by relevance) + ctx.register_skill untuk plugin | 169 skills installed di ~/.hermes/skills; beberapa disabled relevan (code-simplification, incremental-implementation). 3 skill baru ditambahkan oleh adopsi ini |
| Plugins | hermes.json catalog + plugins/<id>/plugin.yaml + update-plugins.sh | nebula aktif. Pola platform di docs/PLUGIN_PLATFORM.md + templates di .github/templates/ |
| MCP servers | hermes mcp (context7, fireflies, twelve-data enabled; lainnya disabled) | context7 aktif = contoh structured docs search. Aktifkan lainnya on-demand, bukan semua |
| LSP | hermes lsp (enabled true; pyright, typescript, rust-analyzer, bash, yaml installed) | Aktif. shellcheck missing = diagnostics bash kosong (warning LSP). |
| Subagents | delegate_task + kanban + hermes -w / --worktree + tmux multi-instance | delegate_task toolset enabled di CLI. Roster subagent didokumentasikan di bawah; belum ada definisi formal .claude/agents, diganti delegate_task goal/context |

## Urutan adopsi (ikut Anthropic: jangan lompat ke MCP sebelum dasar jalan)

1. Project context lean + layered (AGENTS.md portable, .hermes.md hierarchical).
2. Hooks untuk perilaku deterministik (lint/format, test scoped, session learnings).
3. Skills untuk expertise on-demand (progressive disclosure).
4. Plugins untuk distribusi (catalog hermes.json, marketplace mental model).
5. MCP untuk tool eksternal (structured search, docs).
6. LSP untuk navigasi symbol-level.
7. Subagents untuk pisah exploration vs editing.

## 1. Project context — CLAUDE.md setara

- Pakai AGENTS.md untuk aturan yang harus portable di agent lain (Claude Code, Codex, OpenCode).
- Pakai .hermes.md untuk aturan Hermes-spesifik yang harus inherit dari parent ke subdir (walks to git root, first match wins).
- Root file = pointer + gotchas saja. Detail ke skill atau subdirectory .hermes.md.
- Scoped commands per subdir. Jangan global full test suite bila perubahan hanya di satu service.
- Codebase map bila struktur folder tidak informatif: tabel isi folder di root, layering satu level per file.
- Review berkala 3-6 bulan: instruksi model lama bisa jadi constraint model baru.

## 2. Hooks — Hermes shell hooks

Aktif saat ini: notify_9r.py untuk pre_llm_call, pre_tool_call, post_tool_call, post_llm_call, pre_approval_request.

Yang perlu ditambahkan (script contoh ada di docs/hooks-examples/):

- post_tool_call: format/lint file yang berubah (ruff black untuk Python sesuai repo), bukan prompting "ingat lint".
- post_llm_call atau pre_approval_request: session learnings capture ke checklist, mirror curatorial behaviour.
- pre_tool_call: gate untuk command destruktif (guard already via approvals smart mode, jangan duplikasi prompt).

Pendaftaran: tambahkan ke ~/.hermes/config.yaml hooks.<event> dengan hermes config set atau hermes hooks doctor setelah edit config. Jangan hand-edit config.yaml dari file tanpa backup. Script hook harus fail-open (exit 0 walau tool gagal) kecuali guard keamanan.

## 3. Skills — progressive disclosure

- Skill = expertise on-demand. Jangan load semua ke AGENTS.md/.hermes.md.
- Skill baru di adopsi ini (global Hermes):
  - agentic-engineering-workflow: Explore-plan-code, TDD commit tests dulu, verification subagents, two-axis review.
  - large-codebase-navigation: layered context, LSP, ignore, scoped test, codebase map.
  - harness-bootstrap: urutan build harness Hermes langkah demistep.
- Skill plugin: tetap via ctx.register_skill di plugins/<id>/__init__.py (contoh nebula).

## 4. Plugins — distribusi

- Satu plugin satu folder plugins/<id>/, satu entri hermes.json, docs trio (README, docs/USAGE.md, skills), tests + e2e bila host behaviour penting.
- Distribusi via managed marketplace mental model: update-plugins.sh sync ke ~/.hermes/plugins/; jangan distribusikan setup tribal hanya di chat.
- Template sudah ada di .github/templates/ (PLUGIN_E2E_STANDARD, PLUGIN_SKILLS, PLUGIN_STATUS_TABLE, PLUGIN_TEST_STANDARD).

## 5. MCP — perluasan terstruktur

- Aktif: context7 (docs retrieval), fireflies (meeting), twelve-data (finance). Ini cukup untuk banyak sesi.
- Prinsip Anthropic: jangan build MCP sebelum basics bekerja. Tambahkan MCP hanya bila Claude/Hermes tidak bisa akses data/internal tool.
- MCP paling berharga untuk codebase besar: structured search, symbol lookup, internal docs/ticketing. Aktifkan on-demand sesuai scope path.

## 6. LSP — navigasi symbol-level

- hermes lsp enabled true. Installed: pyright, typescript, rust-analyzer, bash-language-server, yaml-language-server.
- Tanpa LSP, grep function umum bisa ribuan matches. Dengan LSP, filtering terjadi sebelum read file.
- Bash LSP warning: shellcheck missing — apt/brew install shellcheck untuk diagnostics bash penuh.
- coding toolset = LSP-backed post-write diagnostics di write_file/patch. Tetap jalankan test/lint secara eksplisit; LSP bukan pengganti test.

## 7. Subagents / paralel — Hermes setara Anthropic

| Butuh | Hermes setara |
|---|---|
| Subagent read-only explorer | delegate_task dengan goal mapping subsystem, read_file/search_files only, tulis findings ke file, return summary |
| Implementer | delegate_task dengan bounded scope, write_file/patch, jalankan scoped test, jangan campur review |
| Reviewer (two-axis) | delegate_task paralel: satu Standards, satu Spec, konteks terpisah. Alternate: hermes -w instance kedua untuk review hasil instance pertama |
| Migrasi / fan-out besar | hermes -w + tmux multi-instance, atau delegate_task paralel 2-4 worker. Queue mechanical: done = file exists on disk |
| Agent teams | kanban board + delegate_task dengan shared task list; cross-session via kanban comment atau file scratchpad bersama |
| Explorer vs editor pisah | Selalu pisahkan bila exploration akan membanjiri konteks utama (search results/log/file dump) |

Roster subagent yang dipakai (di-load via skill agentic-engineering-workflow):

- explorer: read-only, mapping, search_files + read_file + grep. Output: file findings + daftar file relevan + pertanyaan terbuka.
- implementer: write scope terbatas, TDD di seam yang disepakati, scoped test command saja.
- standards-review: cek coding standards + Fowler smells, tidak cek spec.
- spec-review: cek fidelitas ke issue/spec, tidak cek style.
- tester-verifier: tulis/jalankan test, verifikasi tidak overfitting, lapor ground truth.

Kapan tidak pakai subagent: task kecil 1-2 file, overhead tidak sepadan.

## 8. Workflow harian (Hermes adaptation)

- Explore, plan, code, commit
  1. Minta read file relevan. Eksplisit: jangan tulis code dulu.
  2. delegate_task explorer untuk pertanyaan kompleks, hemat konteks utama.
  3. Minta plan. Pakai "think" bila perlu reasoning budget lebih.
  4. Simpan plan ke issue/docs bila masuk akal, agar bisa reset.
  5. Implement, verifikasi penalaran semasa implementasi.
  6. Commit atomik + PR + update docs.

- TDD favorit Anthropic
  1. Minta tests dari input/output pairs. Eksplisit TDD, jangan buat mock implementation.
  2. Run tests, konfirmasi fail.
  3. Commit tests.
  4. Tulis code yang pass tests, jangan ubah tests. Iterate sampai pass.
  5. Verifikasi dengan subagent independen anti-overfitting.
  6. Commit code.

- Praktik Hermes spesifik:
  - hermes chat -q / -z untuk headless one-shot. Tambah --max-turns dan --toolsets sesuai kebutuhan.
  - hermes -w untuk isolated git worktree per sesi paralel.
  - /clear (reset context) atau sesi baru antar task besar; jangan biarkan konteks penuh dengan file dump lama.
  - Checkpoints: hermes chat --checkpoints untuk filesystem rollback sebelum operasi destruktif.
  - Approvals mode smart aktif; jangan aktifkan YOLO di luar container/container throwaway.
  - Kanban untuk multi-agent work queue; satu task per worker, update checklist file bila loop panjang.

## 9. Ownership / governance (Anthropic large org pattern)

- Minimal viable owner: satu DRI (designated responsible individual) untuk harness: settings, permissions, plugin catalog, konvensi .hermes.md/AGENTS.md.
- Tanpa DRI, adopsi bottoms-up fragment dan jadi tribal.
- Cross-functional working group awal: engineering + security + governance untuk approved skills/plugins dan review process.

## Checklist adopsi minimal untuk repo ini

- [x] AGENTS.md portable ada; .hermes.md hierarchical dibuat di root repo ini
- [x] docs/AGENTIC_HARNESS.md kanonis dibuat (file ini)
- [x] docs/hooks-examples/ dengan contoh lint/test/session-logging scripts
- [x] 3 skill global Hermes: agentic-engineering-workflow, large-codebase-navigation, harness-bootstrap
- [x] MCP context7 aktif untuk docs; lainnya tetap disabled sampai dibutuhkan
- [x] LSP enabled; shellcheck install disarankan
- [x] Subagent roster terdokumentasi; delegation toolset sudah enabled
- [x] Aktifkan hook lint/test setelah review script dan hermes config/hooks registration (2026-11-06: script `post_tool_call_lint.py` + `post_llm_call_session_notes.py` diregistrasi via `hermes config set hooks.post_tool_call/hooks.post_llm_call`, diallowlist via `HERMES_ACCEPT_HOOKS=1 hermes hooks doctor`, `hermes hooks test post_tool_call/post_llm_call` exit 0)
- [x] Enable skills incremental-implementation dan code-simplification bila dipakai aktif (2026-11-06: keduanya dihapus dari `skills.disabled` via `hermes config set`, `hermes skills list` = enabled)
- [x] Tambah scoped test/lint commands per subdir ke .hermes.md tiap plugin saat pola stabil (2026-11-06: `.hermes.md` nebula kini memuat syntax/lint compileall, unit tests + deselect pathological, E2E pin, pip-audit — sinkron CI)
- [x] Bentuk .claude/agents formal? -> diganti delegate_task + kanban untuk Hermes; tidak perlu dibuat (keputusan: tidak dibuat; roster `delegate_task` di §7 cukup)

