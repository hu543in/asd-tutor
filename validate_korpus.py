"""Periksa seluruh korpus terhadap aturan ujaran dan kelengkapan data.

Pemakaian:  python validate_korpus.py
Keluar dengan kode 1 jika ada galat.
"""
import sys

from korpus_lib import periksa_entri, semua_entri


def main() -> int:
    ada_galat = False
    for jenis in ("task_analysis", "strategi", "bank_ujaran"):
        for d in semua_entri(jenis, termasuk_draft=True):
            galat, peringatan = periksa_entri(d)
            tanda = "GALAT" if galat else ("CEK" if peringatan else "OK")
            print(f"[{tanda:5}] {d.get('id', d['_file']):12} status={d.get('status')}")
            for g in galat:
                print(f"         galat: {g}")
            for p in peringatan:
                print(f"         cek  : {p}")
            ada_galat |= bool(galat)
    return 1 if ada_galat else 0


if __name__ == "__main__":
    sys.exit(main())
