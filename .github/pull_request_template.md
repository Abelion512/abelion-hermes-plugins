<!-- Setiap PR WAJIB mengisi bagian Fungsi, Alasan merge, dan Bukti verifikasi sebelum request review. Workflow pr-body-check akan menolak bagian yang kosong.
     PR tanpa jawaban Fungsi + Kenapa harus merge = belum siap review. -->

## Fungsi apa yang dibawa PR ini?

<!-- Tulis 1-3 kalimat: perilaku/fungsi baru apa yang berubah? File/path apa?
     Bedakan runtime code vs docs/config/host-state. Contoh buruk: "update docs".
     Contoh baik: "Menambahkan post_tool_call hook yang menjalankan ruff check
     pada .py yang baru ditulis (fail-open); tanpa perubahan runtime plugin." -->

## Kenapa harus saya merge?

<!-- Tulis kenapa ini perlu masuk sekarang: masalah apa yang ditutup, risiko merge
     (rendah/sedang/tinggi + kenapa), urutan stack bila ada (PR ini di atas PR mana),
     dan apa akibat kalau TIDAK di-merge (mis. checklist tetap terbuka, drift). -->

## Bukti verifikasi

<!-- Satu baris bukti nyata per klaim, berlabel:
     TERVERIFIKASI (command + output) / PERKIRAAN / GAGAL.
     Contoh: pytest ... -> 421 passed, 8 skipped; helm/hooks doctor -> OK (link). -->
