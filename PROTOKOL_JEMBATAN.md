# Protokol WebSocket jembatan metaverse

Dokumen ini untuk pengembang klien metaverse (Unity, Godot, web, dll.). Semua pesan adalah satu objek JSON per frame teks.

## Sambungan

```
ws://<host>:8765/ws/metaverse?anak=<ID pseudonim>&token=<token jembatan>
```

- `anak` harus ada di `data/profil.json`. Di mode dev hanya profil bertanda `"uji": true` yang diterima (HTTP 403 jika tidak).
- Token dicetak saat `jembatan.py` dijalankan (disimpan di `data/.jembatan_token`). Token salah ditolak dengan HTTP 401.
- Untuk akses dari luar server, pasang TLS (wss://) di depan jembatan, misalnya lewat nginx. Jangan membuka port 8765 tanpa TLS jika data anak nyata dipakai.

## Metaverse → jembatan

| Pesan | Arti | Diteruskan ke tutor sebagai |
|---|---|---|
| `{"tipe":"respons","nilai":"benar"}` | anak melakukan langkah dengan benar | `[SISTEM] respons=benar` |
| `{"tipe":"respons","nilai":"keliru"}` | anak melakukan hal lain | `[SISTEM] respons=keliru` |
| `{"tipe":"respons","nilai":"tidak_ada"}` | tidak ada respons dalam `jeda_detik` profil | `[SISTEM] respons=tidak_ada` |
| `{"tipe":"lanjut"}` | langkah informasi sudah ditampilkan | `[SISTEM] lanjut` |
| `{"tipe":"regulasi","nilai":"kuning"}` atau `"merah"` | status regulasi dari sensor atau pengamatan | `[SISTEM] regulasi=...` |
| `{"tipe":"anak","teks":"..."}` | transkrip ucapan anak (maks. 200 karakter) | `[ANAK] ...` (tanda `[ ] { } < >` dihapus) |
| `{"tipe":"selesai_diputar"}` | audio avatar selesai diputar (dicadangkan) | tidak diteruskan |

Acara diabaikan (dan guru diberi tahu) jika belum ada sesi yang dimulai guru, atau jika guru menekan HENTIKAN. Pengecualian: `regulasi` tetap diteruskan saat dijeda.

## Jembatan → metaverse

Jawaban tutor yang sudah lolos penjaga:

```json
{"tipe":"tutor","giliran":3,"pujian":"Hebat!","ucap":"Basahi tanganmu.","kartu":"Tangan di bawah air","aksi":"tunggu","ta":"TA-02","langkah":2}
```

Yang dilakukan klien:

1. Putar `pujian` (jika tidak kosong), lalu `ucap` (jika tidak kosong) lewat suara avatar, persis seperti tertulis.
2. Tampilkan kartu gambar `kartu`.
3. Jalankan `aksi`:
   - `tunggu`: tunggu respons anak selama `jeda_detik`, lalu kirim `respons`.
   - `ulang`: ulangi `ucap` dengan kartu disorot.
   - `contohkan`: avatar memperagakan gerakan, lalu tunggu respons.
   - `panggil_guru`: avatar diam dan menampilkan isyarat netral. Guru sudah diberi tanda di dasbor.
   - `tunggu_guru`: avatar diam sampai ada pesan `tutor` berikutnya.
   - `selesai`: tampilkan layar selesai.
   - `lapor`: tidak ada yang diucapkan ke anak.

`catatan_guru` tidak pernah dikirim ke metaverse.

Latar ruangan:

```json
{"tipe":"latar","nilai":"wastafel"}
```

Ganti latar ruangan ke salah satu id di `static/aset/latar/latar.json` (`kelas`, `pintu`, `wastafel`, `bermain`,
`tenang`). Dikirim saat guru menekan MULAI (latar dari `peta_ta` untuk TA itu, kecuali guru memilih latar
sendiri), saat guru mengganti latar di dasbor, dan sekali saat klien tersambung bila latar sudah ditetapkan.
Posisi avatar dan papan kartu tidak berubah. Dari dasbor: `{"tipe":"latar","nilai":"<id>|otomatis"}`.

Perintah dari guru:

```json
{"tipe":"diam"}
```

Hentikan audio yang sedang diputar dan diam sampai ada pesan `tutor` berikutnya.

Galat:

```json
{"tipe":"galat","pesan":"..."}
```

Pesan dari klien tidak dikenali. Kirim ulang dengan format yang benar.

## Urutan contoh

```
guru     → {"tipe":"mulai","ta":"TA-02","fase":"B"}        (dari dasbor)
avatar   ← {"tipe":"tutor","ucap":"Buka keran.","aksi":"tunggu",...}
metaverse→ {"tipe":"respons","nilai":"benar"}
avatar   ← {"tipe":"tutor","pujian":"Bagus!","ucap":"Basahi tanganmu.","aksi":"tunggu",...}
metaverse→ {"tipe":"respons","nilai":"tidak_ada"}
avatar   ← {"tipe":"tutor","ucap":"Basahi tanganmu.","aksi":"ulang",...}
```

## Klien rujukan

`static/metaverse.html` (A-Frame) adalah contoh klien lengkap yang mengikuti protokol ini, termasuk
`selesai_diputar` setelah audio selesai dan penanganan `diam`.
