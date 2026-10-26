screen (v0.6.3-20261026) - Screen plugin untuk dashboard Hermes

Isi: menu SCREEN di sidebar dashboard Hermes - pantau layar Bot Screen
(virtual desktop + browser milik agent), Take over untuk klik/ketik,
Hand back untuk mengembalikan kendali ke agent.

Pasang (repo private, pakai akses GitHub yang tersimpan di laptop):
  hermes plugins install --enable Abelion512/abelion-hermes-plugins/screen
atau dari clone repo ini:
  bash screen/install.sh

Syarat: hermes dashboard jalan; Bot Screen/desktop agent aktif
(hermes computer-use screen start bila belum). Tidak menyentuh file inti
Hermes. Copot: hermes plugins remove screen  (atau bash screen/uninstall.sh)
