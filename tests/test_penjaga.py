"""Uji unit penjaga keluaran.  Jalankan:  ./venv/bin/python tests/test_penjaga.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from penjaga import Penjaga  # noqa: E402

dev = Penjaga(mode="dev", log=False)
dev_bank = Penjaga(mode="dev", bank="draft", log=False)
prod = Penjaga(mode="prod", log=False)


def J(**k):
    base = {"pujian": "", "ucap": "", "kartu": "", "aksi": "tunggu", "ta": "TA-02", "langkah": 1, "catatan_guru": ""}
    base.update(k)
    return json.dumps(base, ensure_ascii=False)


KASUS = [
    # (nama, penjaga, jawaban, harus_lolos, potongan_pesan_yang_diharapkan)
    ("jawaban skenario 1 langkah 1", dev, J(ucap="Buka keran.", kartu="Tangan memutar keran"), True, None),
    ("pujian sementara + langkah 2", dev, J(pujian="Hebat!", ucap="Basahi tanganmu.", langkah=2), True, None),
    ("beda huruf besar dan titik tetap lolos", dev, J(ucap="buka keran", langkah=1), True, None),
    ("placeholder terisi dari profil", dev, J(ucap="Keringkan tangan dengan handuk.", langkah=9), True, None),
    ("eskalasi dengan ucap kosong", dev, J(aksi="panggil_guru"), True, None),
    ("TA-09 langkah benda kesukaan", dev, J(ucap="Pegang bola karet.", ta="TA-09", langkah=4), True, None),
    ("kalimat karangan diblokir", dev, J(ucap="Ayo buka kerannya, pintar!"), False, "di luar korpus"),
    ("tambahan satu kata diblokir", dev, J(ucap="Buka keran sekarang."), False, "di luar korpus"),
    ("pujian karangan diblokir", dev, J(pujian="Wah, kamu anak pintar sekali!", ucap="Basahi tanganmu."), False, "pujian"),
    ("placeholder mentah diblokir", dev, J(ucap="Keringkan tangan dengan [pengering kelas]."), False, "placeholder"),
    ("placeholder kosong di profil diblokir", dev, J(ucap="Tunjuk gambar [aktivitas sekarang].", ta="TA-08"), False, "placeholder"),
    ("ucap saat panggil_guru diblokir", dev, J(ucap="Buka keran.", aksi="panggil_guru"), False, "harus kosong"),
    ("aksi tidak dikenal diblokir", dev, J(ucap="Buka keran.", aksi="ngobrol"), False, "aksi"),
    ("bukan JSON diblokir", dev, "Halo! Ayo kita cuci tangan.", False, "bukan objek JSON"),
    ("jawaban lelucon diblokir", dev, J(ucap="Kenapa ayam menyeberang jalan?", aksi="ulang"), False, "di luar korpus"),
    ("bank draft tidak dipakai bawaan", dev, J(ucap="Coba lagi, ya.", aksi="ulang"), False, "di luar korpus"),
    ("bank draft boleh dengan ASD_RAG_BANK=draft", dev_bank, J(ucap="Coba lagi, ya.", aksi="ulang"), True, None),
    ("prod: TA berstatus valid dimuat", prod, J(ucap="Buka keran."), True, None),
    ("prod: bank draft tidak dimuat", prod, J(ucap="Coba lagi, ya.", aksi="ulang"), False, "di luar korpus"),
    ("prod: pujian sementara tetap ada", prod, J(pujian="Bagus!", aksi="selesai"), True, None),
]

PERINGATAN = [
    ("langkah tidak cocok", dev, J(ucap="Ambil sabun.", langkah=1), "langkah 3"),
    ("TA lain", dev, J(ucap="Pegang bola karet.", ta="TA-02"), "TA-09"),
    ("langkah di atas level anak", dev, J(ucap="Gosok sela jarimu.", langkah=6), "nonaktif"),
    ("teks di luar JSON", dev, 'Baik. ' + J(ucap="Buka keran."), "di luar objek JSON"),
]

gagal = 0
for nama, p, jw, harus, pesan in KASUS:
    h = p.periksa(jw, "A01")
    ok = h["lolos"] == harus and (pesan is None or any(pesan in x for x in h["pelanggaran"]))
    if not h["lolos"]:
        ok &= h["keluaran"]["ucap"] == "" and h["keluaran"]["aksi"] == "panggil_guru"
    gagal += not ok
    print(f"{'OK  ' if ok else 'GAGAL'} {nama}" + ("" if ok else f"\n      {h}"))

for nama, p, jw, pesan in PERINGATAN:
    h = p.periksa(jw, "A01")
    ok = h["lolos"] and any(pesan in x for x in h["peringatan"])
    gagal += not ok
    print(f"{'OK  ' if ok else 'GAGAL'} peringatan: {nama}" + ("" if ok else f"\n      {h}"))

h = dev.periksa(J(ucap="buka keran"), "A01")
ok = h["keluaran"]["ucap"] == "Buka keran."
gagal += not ok
print(f"{'OK  ' if ok else 'GAGAL'} ucap dinormalkan ke bentuk korpus")

print(f"\n{len(KASUS) + len(PERINGATAN) + 1 - gagal} dari {len(KASUS) + len(PERINGATAN) + 1} lulus")
sys.exit(1 if gagal else 0)
