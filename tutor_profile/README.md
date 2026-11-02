# Profil Hermes `tutor-asd`

Profil terpisah untuk tutor yang berinteraksi dengan anak. Berbeda dari profil pengembang (default),
profil ini **hanya** bisa memakai lima tool `asd_rag`. Terminal, file, web, browser, memori, skill,
eksekusi kode, dan delegasi dimatikan.

| File | Fungsi |
|---|---|
| `SOUL.md` | Identitas, aturan mutlak, protokol pesan `[GURU]/[ANAK]/[SISTEM]`, keluaran JSON, prosedur sesi |
| `setup_tutor_profile.py` | Mengunci config profil (model, tool, skill) dan menyalin SOUL.md serta API key |
| `skenario_uji.md` | 13 skenario uji perilaku untuk dicatat Lulus/Gagal |
| `uji_tutor.py` | Menjalankan ke-13 skenario lewat Hermes CLI, atau lewat API server dengan `--api`; setiap jawaban juga diperiksa penjaga |

## Catatan desain

Prosedur sesi ditulis di `SOUL.md`, bukan sebagai skill. Toolset `skills` sengaja dimatikan agar tutor
tidak bisa membuat atau mengubah skill sendiri (fitur belajar otomatis Hermes). `SOUL.md` selalu dimuat
di posisi pertama system prompt, sehingga prosedur tidak bergantung pada pemanggilan skill.

Profil Hermes mengisolasi pengaturan, tetapi bukan sandbox. Pengamanan utamanya adalah daftar tool
yang dibatasi ditambah mode `prod` di server `asd_rag`.

## Pemasangan

```bash
# 1. buat profil kosong
hermes profile create tutor-asd

# 2. kunci profil
~/asd-rag/venv/bin/python ~/asd-rag/tutor_profile/setup_tutor_profile.py

# 3. periksa
hermes -p tutor-asd config check
hermes -p tutor-asd mcp test asd_rag

# 4. jalankan; banner harus hanya menampilkan tool Asd Rag
hermes -p tutor-asd --tui
```

Disarankan memakai API key Anthropic terpisah untuk tutor: ganti nilai `ANTHROPIC_API_KEY` di
`~/.hermes/profiles/tutor-asd/.env`.

## Uji otomatis

```bash
# sekali saja: cari cara melanjutkan sesi Hermes yang berlaku di versi Anda
~/asd-rag/venv/bin/python ~/asd-rag/tutor_profile/uji_tutor.py --probe

# semua skenario (20-40 menit), atau sebagian: -s 1 4 12
~/asd-rag/venv/bin/python ~/asd-rag/tutor_profile/uji_tutor.py
```

Hasil tersimpan di `~/asd-rag/data/uji_tutor_<waktu>.csv` dan `.jsonl`. Jalankan ulang setiap kali
SOUL.md, korpus, atau model berubah.
