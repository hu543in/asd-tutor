# Latar ruangan

`latar.json` berisi lima latar: `kelas`, `pintu` (pintu kelas dan loker), `wastafel`, `bermain` (area bermain),
`tenang` (sudut tenang). Latar dipilih otomatis dari `peta_ta` saat guru menekan MULAI, atau dipilih guru lewat
menu "Latar ruangan" di dasbor ("Otomatis (ikut TA)" mengembalikan ke peta).

| TA | Latar |
|---|---|
| TA-01, TA-05 | pintu |
| TA-02 | wastafel |
| TA-03, TA-04, TA-06, TA-08, TA-10 | kelas |
| TA-07 | bermain |
| TA-09 | tenang |

Peta mengikuti kolom `setting` di YAML task analysis.

## Mengubah

- Warna, benda, atau peta TA: ubah `alat/latar/buat_latar.py`, lalu jalankan `python alat/latar/buat_latar.py`.
  Mengedit `latar.json` langsung juga boleh. Jembatan membaca daftar latar saat dijalankan, jadi restart
  `asd-jembatan` setelah menambah latar atau mengubah peta; perubahan warna cukup dengan memuat ulang halaman.
- Elemen yang dipakai: plane, box, cylinder, sphere, circle, cone, ring, torus, entity. Atribut: position,
  rotation, scale, width, height, depth, radius*, color, opacity. Atribut lain diabaikan.
- Model 3D opsional per latar: taruh berkas .glb di folder ini dan tambahkan
  `"model": {"berkas": "kantin.glb", "position": "0 0 -1.5", "scale": "1 1 1"}` pada latar itu.
  Pastikan lisensi model mengizinkan pemakaian dan catat kreditnya.

## Prinsip

Posisi avatar (-1,25; 0; -2,6) dan papan kartu (1,0; 1,65; -3,1) sama di semua latar, agar anak selalu tahu
di mana melihat. Jangan menaruh benda di antara kamera dan keduanya. Warna lembut, sedikit benda, tanpa cahaya
berkedip atau benda bergerak. Pergantian latar memakai tirai pelan 0,5 detik, atau langsung bila "Kurangi
gerakan" aktif.
