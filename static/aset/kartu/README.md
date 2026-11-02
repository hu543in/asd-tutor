# Gambar kartu

Klien metaverse menampilkan gambar kartu bila gambarnya **sudah disetujui guru** di `kartu.json`.
Kartu tanpa gambar yang disetujui tetap tampil sebagai teks.

```bash
cd ~/asd-rag
./venv/bin/python kartu.py daftar                      # buat kartu.json dari korpus dan lihat statusnya
./venv/bin/python kartu.py kandidat -n 6               # cari piktogram ARASAAC untuk semua kartu tanpa gambar
#   buka https://<domain>/aset/kartu/_kandidat/index.html, pilih ID untuk tiap kartu
./venv/bin/python kartu.py pasang --kartu "Pintu kelas" --id 1234
./venv/bin/python kartu.py setujui --kartu "Pintu kelas"
```

Gambar sendiri (mis. foto wastafel atau loker di sekolah, tanpa wajah anak): salin ke folder ini lalu
`kartu.py sendiri --kartu "Tangan di bawah air" --berkas wastafel.jpg` dan `kartu.py setujui ...`.

Kata kunci pencarian ARASAAC (bahasa Inggris) bisa diubah di kolom `kata_kunci` pada `kartu.json`.
Nama kartu dengan `[placeholder]`, mis. `Tangan di [pengering kelas]`, berlaku untuk isian profil apa pun.

Lisensi piktogram ARASAAC: penulis Sergio Palao, asal ARASAAC (https://arasaac.org), milik Pemerintah
Aragon (Spanyol), CC BY-NC-SA 4.0. Hanya untuk penggunaan nonkomersial, sumber wajib dicantumkan
(Panel guru di klien menampilkannya otomatis), dan karya turunan memakai lisensi yang sama.

## Piktogram buatan proyek (`buatan/`)

19 piktogram digambar khusus untuk kartu yang tidak punya padanan cocok di ARASAAC (cuci tangan, loker,
tas, papan jadwal, kartu istirahat, dan lain-lain). Lisensi CC0; sumber gambarnya ada di
`alat/piktogram/gambar.js` sehingga bisa diubah dan digambar ulang.

```bash
./venv/bin/python kartu.py buatan          # pasang ke kartunya (belum disetujui)
#   tinjau di https://<domain>/aset/kartu/_kandidat/buatan.html
./venv/bin/python kartu.py setujui --kartu "Papan jadwal" --kartu "Tangan melambai"
```

## Foto sekolah

Untuk benda dan tempat milik sekolah (loker, kursi, tas, kotak bekal, wastafel, pengering, papan jadwal),
foto benda yang sebenarnya biasanya lebih mudah dikenali anak daripada piktogram. Foto hanya benda atau
tangan orang dewasa; jangan memuat wajah atau nama anak. Untuk "Loker dengan foto anak" dan
"Kursi dengan foto anak", pakai foto loker atau kursi dengan stiker simbol pengganti, bukan foto wajah anak.
