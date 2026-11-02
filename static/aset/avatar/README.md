# Avatar manusia 3D untuk klien metaverse

Klien `metaverse.html` memakai avatar 3D bila folder ini berisi `avatar.json` dan file model yang disebut di
dalamnya. Tanpa keduanya, avatar sederhana dipakai.

## Langkah

1. Siapkan model **GLB** (glTF biner) dengan rangka dan animasi. Jangan memakai kompresi Draco atau meshopt.
2. Salin ke folder ini, misalnya `guru.glb`.
3. Periksa nama animasi dan morph target:
   `~/asd-rag/venv/bin/python ~/asd-rag/periksa_avatar.py ~/asd-rag/static/aset/avatar/guru.glb`
4. Salin `avatar.contoh.json` menjadi `avatar.json`, lalu isi `klip` dengan potongan nama animasi model itu
   (pencocokan tidak peka huruf besar dan cukup sebagian nama, mis. `"Idle"` cocok dengan
   `"CharacterArmature|Idle"`).
   - `diam`: animasi berdiri tenang (wajib agar avatar tidak kaku)
   - `bicara`: animasi berbicara (opsional)
   - `contohkan`: gerakan memperagakan atau menunjuk, dipakai untuk aksi `contohkan` (opsional)
   - `morfMulut`: nama morph target mulut (opsional; mis. `jawOpen` pada model bergaya ARKit)
5. Muat ulang halaman `/metaverse`. Baris "Avatar 3D: …" di Panel guru menunjukkan animasi yang ditemukan.

Model tanpa morph mulut (banyak model Sketchfab): isi `mulutOverlay` dengan nama bagian mulut atau gigi
(lihat baris "Bagian" dari `periksa_avatar.py`). Klien menggambar rongga mulut gelap di depan bagian itu yang
membuka-menutup mengikuti ucapan. Model tanpa animasi bergoyang sangat pelan dan menoleh ke papan kartu saat
aksi `contohkan`. Isi `kredit` untuk model berlisensi CC BY; teksnya tampil di Panel guru.

Model dengan material lama (spec-gloss) harus dikonversi dulu:
`npx @gltf-transform/cli metalrough masukan.glb guru.glb`.

Tinggi model diskalakan otomatis ke `tinggi` (meter) dan kakinya diletakkan di lantai. Ubah `rotasiY` (derajat)
bila avatar membelakangi kamera.

## Memilih model

- Pilih tokoh bergaya sederhana dengan ekspresi tenang, pakaian polos, dan warna lembut. Wajah yang sangat
  realistis atau berlebihan dapat terasa janggal atau mengganggu bagi sebagian anak autis.
- Pakai avatar yang sama di setiap sesi agar anak dapat mengenalinya.
- Catat sumber dan lisensi model untuk disertasi. Periksa lisensi di halaman unduhan; aset berlisensi CC0
  paling sederhana.
- Avatar yang dibuat dari foto orang sungguhan (mis. guru) memerlukan persetujuan tertulis orang tersebut.
