# Hermes Hooks Examples — Anthropic "hooks for deterministic behavior"

Contoh script, bukan config aktif. Belum diregistrasi ke ~/.hermes/config.yaml.

## Cara aktifkan

1. Review script. Pastikan fail-open dan command tidak destruktif.
2. Salin ke ~/.hermes/hooks/ dengan chmod +x.
3. Tambah ke config.yaml hooks.<event> dengan hermes config edit atau hermes hooks tool bila tersedia.
4. Verifikasi dengan hermes hooks list / hermes hooks doctor.
5. Restart gateway/agent bila perlu dan jalankan satu tool call sederhana untuk smoke test.

## Prinsip Anthropic yang diadaptasi

- Lint/format/test di hook, bukan di prompt model.
- Stop/post_llm_call hook untuk propose CLAUDE.md update (di sini .hermes.md/AGENTS.md), jangan auto-overwrite.
- Hook harus deterministik dan auditable. Guard keamanan boleh exit 2; hook info harus fail-open.
