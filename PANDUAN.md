# asd-rag — Server MCP Pedagogical RAG untuk Hermes Agent

Server ini memberi Hermes lima tool. Task analysis diambil **secara pasti berdasarkan ID**
dan ujarannya diucapkan apa adanya; pencarian vektor hanya untuk strategi.

| Tool | Fungsi |
|---|---|
| `ambil_task_analysis(id_ta, id_anak)` | Langkah dan ujaran persis dari korpus; placeholder diisi dari profil anak |
| `cari_strategi(pertanyaan, domain)` | Pencarian hibrida (semantik + kecocokan kata) atas strategi dan task analysis |
| `profil_anak(id_anak)` | Profil pseudonim |
| `catat_langkah(sesi_id, id_anak, id_ta, nomor_langkah, skor, fase)` | Log M/MB/BM per langkah untuk SSR (A1/B/A2); `sesi_id` wajib |
| `panggil_guru(id_anak, alasan, tingkat)` | Eskalasi; opsional dikirim ke webhook |

## Mode keamanan

- `ASD_RAG_MODE=prod` (bawaan): hanya entri `status: valid` yang dimuat. Entri valid wajib
  memiliki data validasi (validator dan Aiken's V).
- `ASD_RAG_MODE=dev`: entri draft ikut dimuat dan setiap hasil diberi PERINGATAN. **Hanya untuk
  profil pengembang, tidak untuk anak.**

## Pemasangan di server

```bash
# 1. salin dan ekstrak paket ke ~/asd-rag
cd ~ && unzip asd-rag.zip && cd ~/asd-rag

# 2. lingkungan Python terpisah dari Hermes
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. periksa korpus terhadap aturan ujaran
./venv/bin/python validate_korpus.py

# 4. bangun indeks (pertama kali mengunduh model embedding sekitar 220 MB)
ASD_RAG_MODE=dev ./venv/bin/python ingest.py

# 5. sambungkan ke Hermes: salin isi hermes_config.yaml ke ~/.hermes/config.yaml
hermes mcp test asd_rag
```

Di dalam Hermes, jalankan `/reload-mcp`, lalu uji:

- "Ambil TA-02 untuk anak A01 dan tampilkan langkah yang aktif."
- "Cari strategi untuk anak yang sulit berpindah aktivitas."
- "Catat langkah 3 TA-02 anak A01 dengan skor MB fase B."

## Pencarian dan evaluasi

Sejak versi 2 paket, setiap entri diindeks sebagai beberapa potongan pendek (inti, isi, langkah),
dan hasil semantik digabung dengan skor kecocokan kata (TF-IDF trigram) memakai Reciprocal Rank Fusion.

```bash
# bandingkan model dan mode pencarian (mengunduh model mpnet sekitar 1 GB pada percobaan pertama)
ASD_RAG_MODE=dev ./venv/bin/python eval_retrieval.py
```

Skrip mencetak Recall@1, Recall@3, dan MRR per konfigurasi, menyimpan `data/eval_retrieval.csv`,
dan mencetak skor kueri di luar cakupan untuk mengkalibrasi ambang `relevan`.

Variabel lingkungan pencarian (diatur di blok `env` config Hermes):

| Variabel | Bawaan | Fungsi |
|---|---|---|
| `ASD_RAG_EMBED_MODEL` | MiniLM multibahasa | Model embedding; harus sama saat ingest dan saat server berjalan |
| `ASD_RAG_SEARCH` | `hibrida` | `hibrida`, `semantik`, atau `kata` |
| `ASD_RAG_T_SEM` | `0.5` | Ambang relevan skor semantik |
| `ASD_RAG_T_KATA` | `0.15` | Ambang relevan skor kata |

Konfigurasi terpilih (evaluasi 27 Okt 2026, 16 kueri, korpus draft 12 entri): mpnet + hibrida,
Recall@1 0,88, Recall@3 1,00, MRR 0,94; ambang semantik 0,52 dan kata 0,26
(1/16 jawaban benar ditandai tidak relevan, 0/4 kueri luar korpus ditandai relevan).
Model disimpan permanen di `models/` agar tidak terunduh ulang.

## Rekap SSR

```bash
./venv/bin/python rekap_ssr.py
```

Membaca `data/log_langkah.jsonl`, memakai skor terakhir per langkah per sesi, hanya sesi lengkap,
dan melewati anak uji. Menghasilkan `data/rekap_sesi.csv` dan `data/rekap_ssr.csv` (rerata per fase,
PND A1 vs B, Tau A vs B tanpa koreksi tren).

## Perubahan versi 5

- `ambil_task_analysis` membuka sesi baru (`sesi_id`) dan menandai `dalam_ta_aktif`; ID anak yang
  tidak dikenal ditolak.
- `catat_langkah` wajib memakai `sesi_id`; waktu log dalam WIB (`ASD_RAG_TZ`).
- SOUL.md: aturan `ta_aktif`, aturan langkah informasi, pemakaian `sesi_id`.
- `rekap_ssr.py` dan `tutor_profile/uji_tutor.py` baru.

## Penjaga keluaran (versi 6)

`penjaga.py` memeriksa setiap jawaban JSON tutor sebelum diteruskan ke metaverse. `ucap` dan
`pujian` hanya lolos jika persis sama (abaikan huruf besar dan tanda baca) dengan:

- `ujaran` langkah task analysis yang dimuat, setelah placeholder diisi dari profil anak;
- bank ujaran `korpus/bank_ujaran/BANK-01.yaml`, hanya bila berstatus `valid`;
- tiga pujian sementara di SOUL.md.

Pelanggaran memblokir seluruh jawaban: yang diteruskan adalah keluaran aman (`ucap: ""`,
`aksi: panggil_guru`) dan alasannya dicatat di `data/penjaga.jsonl`. Pelanggaran yang diperiksa:
kalimat di luar daftar, placeholder belum terisi, `ucap` terisi saat `panggil_guru`/`tunggu_guru`/`lapor`,
`aksi` tidak dikenal, dan jawaban yang bukan JSON. Ucapan dari langkah atau TA lain, langkah di atas level
anak, dan kartu yang tidak dikenal hanya diberi peringatan.

```bash
./venv/bin/python tests/test_penjaga.py                                  # 24 uji unit
ASD_RAG_MODE=dev ./venv/bin/python penjaga.py --anak A01 --daftar        # kalimat yang diizinkan untuk A01
ASD_RAG_MODE=dev ./venv/bin/python penjaga.py --uji data/uji_tutor_<waktu>.jsonl   # periksa ulang uji lama
```

`tutor_profile/uji_tutor.py` kini menjalankan penjaga pada setiap jawaban; jawaban yang diblokir
dihitung Gagal. Jembatan metaverse (Langkah 8) wajib memanggil `Penjaga(eskalasi=True).periksa(...)`
dan hanya meneruskan `hasil["keluaran"]`.

## Jembatan metaverse (versi 7)

`jembatan.py` menghubungkan metaverse dan dasbor guru dengan tutor lewat WebSocket. Tutor dihubungi
lewat API server Hermes (`hermes -p tutor-asd gateway`, port 8643, hanya 127.0.0.1), sehingga server
MCP tetap hangat dan setiap giliran jauh lebih cepat daripada CLI. Setiap jawaban tutor melewati
`penjaga.py`, dan metaverse hanya menerima keluaran yang aman, tanpa `catatan_guru`.
Protokol untuk pengembang metaverse: `PROTOKOL_JEMBATAN.md`.

| File | Fungsi |
|---|---|
| `jembatan.py` | Server WebSocket `/ws/metaverse`, `/ws/guru`, dasbor `/guru`, log `data/jembatan.jsonl` |
| `hermes_klien.py` | Penggerak tutor: `api` (bawaan), `cli` (cadangan), `palsu` (uji tanpa Hermes) |
| `static/guru.html` | Dasbor guru: MULAI, SETUJU, LANJUT, SELESAI, HENTIKAN, simulasi metaverse, catatan giliran |
| `tests/test_jembatan.py` | 16 uji alur dengan penggerak palsu |
| `tests/test_hermes_klien.py` | 8 uji pembaca jawaban API server (bentuk asli Hermes 0.21) |

Variabel lingkungan: `ASD_RAG_MODE` (samakan dengan server MCP), `JEMBATAN_HOST` (bawaan 127.0.0.1),
`JEMBATAN_PORT` (8765), `JEMBATAN_TOKEN` (bawaan: dibuat sekali di `data/.jembatan_token`),
`JEMBATAN_PENGGERAK` (`api`, `cli`, `palsu`), `JEMBATAN_BATAS_WAKTU` (120 detik).

Saat mulai, jembatan menolak berjalan jika API server tidak bisa dihubungi atau jika tutor punya tool
selain `asd_rag` lewat API server.

## Server produksi (versi 7.2)

Salinan konfigurasi server yang terpasang ada di folder `deploy/`:

| File | Tujuan di server | Fungsi |
|---|---|---|
| `hermes-tutor.service` | `/etc/systemd/system/` | Gateway profil tutor-asd menyala otomatis |
| `asd-jembatan.service` | `/etc/systemd/system/` | Jembatan menyala otomatis, hanya boleh menulis ke `data/` |
| `Caddyfile` | `/etc/caddy/` | HTTPS Let's Encrypt untuk `domain-anda.duckdns.org` |
| `00-asd-hardening.conf` | `/etc/ssh/sshd_config.d/` | SSH hanya dengan kunci |
| `asd-sshd.local` | `/etc/fail2ban/jail.d/` | Blokir IP setelah 5 kali gagal login |

Perintah sehari-hari: `systemctl status hermes-tutor asd-jembatan`, `journalctl -u asd-jembatan -f`,
`sudo systemctl restart asd-jembatan` (setelah memperbarui kode).

Hemat memori: model embedding hanya dimuat saat `cari_strategi` dipanggil (`ASD_RAG_PEMANASAN=1` untuk
memuatnya saat server MCP menyala). Profil tutor tidak diberi `cari_strategi`.

## Panggilan guru dan login dasbor (versi 7.3)

- Tool `panggil_guru` di server MCP mengirim panggilan ke jembatan (`ASD_RAG_WEBHOOK` =
  `http://127.0.0.1:8765/internal/panggil_guru`, token dari `data/.jembatan_token`). Dasbor menampilkan
  tingkatnya; tingkat tinggi berwarna merah dan berbunyi. Jalur `/internal/*` ditolak bila datang lewat
  Caddy, tanpa token, atau dari luar server.
- Dasbor guru diberi kata sandi tambahan (basic_auth Caddy) untuk `/guru`, `/api/*`, `/ws/guru`.
  Jalur `/ws/metaverse` tetap memakai token jembatan.

## Klien metaverse A-Frame (versi 8)

`static/metaverse.html`, dibuka di `https://<domain>/metaverse` pada perangkat anak. Guru mengisi ID anak dan
token jembatan, lalu menekan Mulai (membuka kunci audio peramban). Isinya:

- Kelas 3D yang tenang (A-Frame 1.6.0, disalin ke `static/aset/vendor/`, lisensi MIT), avatar tutor, papan kartu.
- Suara: Web Speech API dengan suara bahasa Indonesia (`id-ID`) bila tersedia di perangkat; jika tidak ada,
  kalimat hanya tampil sebagai teks. Kalimat diputar persis seperti diterima dari jembatan.
- Aksi: `ulang` menyorot kartu, `contohkan` menggerakkan lengan avatar, `panggil_guru`/`tunggu_guru` menampilkan
  jam pasir tanpa kata, `selesai` menampilkan lingkaran hijau, `diam` menghentikan suara.
- Panel guru (tersembunyi) untuk mengirim respons benar/keliru/tidak ada/lanjut dan regulasi kuning/merah.
- Pilihan "Kurangi gerakan" dan dukungan `prefers-reduced-motion`; tombol VR untuk headset WebXR.

Avatar manusia 3D (v8.1): taruh model GLB dan `avatar.json` di `static/aset/avatar/` (lihat README di folder
itu, dan `periksa_avatar.py` untuk melihat nama animasinya). Tanpa model, avatar sederhana dipakai.
v8.6: paket menyertakan avatar "Teacher_Joe" (Joe chakrapong, CC BY 4.0; lihat `static/aset/avatar/KREDIT.txt`)
dengan gerak mulut berupa rongga mulut yang mengikuti ucapan.

Gambar kartu (v8.2): `kartu.py` mengelola gambar untuk setiap nama kartu di korpus (piktogram ARASAAC atau foto
sendiri). Gambar hanya tampil ke anak setelah disetujui guru. v8.3: beberapa kata kunci per kartu
(`daftar --kata-baru`) dan dua gambar buatan untuk kartu konsep abstrak. Lihat `static/aset/kartu/README.md`.

Belum ada: deteksi respons otomatis (sengaja, guru yang menilai), pengenalan ucapan anak (layanan STT awan
mengirim suara anak ke pihak ketiga; perlu STT di perangkat), dan gambar kartu yang sudah disetujui (sampai disetujui, kartu berupa teks).

## Profil tutor

Folder `tutor_profile/` berisi persona, skrip penguncian, dan skenario uji untuk profil Hermes `tutor-asd`. Lihat `tutor_profile/README.md`.

## Struktur

```
korpus/task_analysis/TA-01..TA-10.yaml   task analysis versi 2 (status: draft)
korpus/strategi/STR-*.yaml               strategi (draft, contoh awal)
korpus/bank_ujaran/BANK-01.yaml          58 kalimat bank ujaran (draft, menunggu validasi)
penjaga.py                               penjaga keluaran tutor
jembatan.py, hermes_klien.py, static/    jembatan metaverse dan dasbor guru
data/jembatan.jsonl                      dibuat otomatis: log setiap giliran jembatan
data/penjaga.jsonl                       dibuat otomatis: jawaban yang diblokir atau diberi peringatan
data/profil.json                         profil pseudonim (A01 = DATA CONTOH)
data/log_langkah.jsonl                   dibuat otomatis: data SSR
data/eskalasi.jsonl                      dibuat otomatis: catatan panggil guru
```

## Setelah validasi selesai

Status per 31 Oktober 2026: TA-01 sampai TA-10 sudah `valid` (Aiken's V, 3 validator, rerata 0,90).
BANK-01 dan strategi masih `draft`. Di mode prod, tutor hanya boleh mengucapkan ujaran langkah TA
dan tiga pujian sementara di SOUL.md. Catatan revisi ada di `korpus/CATATAN_REVISI_TA_v3.md`.

1. Isi `validasi` (validator, aiken_v, tanggal) di tiap YAML yang lolos, ubah `status: valid`.
   Bank ujaran juga: setelah BANK-01 valid, perbarui daftar Pujian di SOUL.md.
2. `./venv/bin/python validate_korpus.py`
3. `./venv/bin/python ingest.py` (mode prod)
4. Ubah `ASD_RAG_MODE` di config Hermes dan di `deploy/asd-jembatan.service` menjadi `prod`.
   Lakukan langkah 4 hanya setelah izin etik dan persetujuan orang tua keluar: mode prod menerima
   profil anak sungguhan.

## Catatan

- Placeholder `[sebutan guru]`, `[pengering kelas]`, `[benda kesukaan]`, `[benda hitung]`,
  `[sapaan singkat]` diisi dari `isian` di profil. Langkah dengan placeholder kosong ditandai
  `siap_diucapkan: false` dan tidak boleh diucapkan.
- `ASD_RAG_WEBHOOK` (opsional): URL untuk meneruskan panggilan guru ke dasbor.
- Paket ini memakai `mcp` versi 1.x; versi 2.x mengubah API FastMCP.
