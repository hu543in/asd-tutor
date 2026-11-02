"""Rekap data SSR dari data/log_langkah.jsonl.

Aturan pembersihan:
  - Rekaman tanpa sesi_id (log versi lama) dilewati.
  - Satu langkah yang tercatat lebih dari sekali dalam satu sesi: dipakai rekaman TERAKHIR.
  - Anak uji (profil bertanda "uji": true, mis. A01) dilewati kecuali --termasuk-uji.
  - Sesi dianggap LENGKAP jika semua langkah aktif (sesuai level anak, tanpa langkah opsional dan
    informasi) sudah tercatat. Hanya sesi lengkap yang masuk analisis fase, kecuali --semua.

Keluaran:
  data/rekap_sesi.csv   satu baris per sesi: tanggal, fase, jumlah M/MB/BM, persen mandiri, lengkap
  data/rekap_ssr.csv    per anak x TA: rerata per fase, PND (A1 vs B), Tau A vs B

Catatan metode: Tau di sini adalah indeks nonoverlap A vs B tanpa koreksi tren baseline
(Tau_AvsB); untuk Tau-U dengan koreksi tren gunakan kalkulator khusus.

Pemakaian:  ./venv/bin/python rekap_ssr.py [--semua]
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict

import re

from korpus_lib import DATA, semua_entri

URUTAN_LEVEL = {"dasar": 0, "menengah": 1, "lanjut": 2}


def _profil() -> dict:
    p = DATA / "profil.json"
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return {re.sub(r"[^A-Za-z0-9]", "", k).upper(): v for k, v in json.load(f).items()}


def langkah_dinilai(id_ta: str, level: str) -> set[int]:
    # definisi langkah dibaca apa pun statusnya (draft/valid), karena ini analisis data yang sudah tercatat
    norm = lambda x: re.sub(r"[^A-Z0-9]", "", x.upper())
    d = next((e for e in semua_entri("task_analysis", termasuk_draft=True) if norm(e["id"]) == norm(id_ta)), {})
    hasil = set()
    for s in d.get("langkah", []):
        if s.get("opsional") or s.get("jenis") == "informasi":
            continue
        lv = s.get("level_min")
        if lv and URUTAN_LEVEL.get(level, 0) < URUTAN_LEVEL.get(lv, 0):
            continue
        hasil.add(s["nomor"])
    return hasil


def pnd(a: list[float], b: list[float]) -> float | None:
    if not a or not b:
        return None
    return 100 * sum(x > max(a) for x in b) / len(b)


def tau_ab(a: list[float], b: list[float]) -> float | None:
    if not a or not b:
        return None
    naik = sum(1 for x in a for y in b if y > x)
    turun = sum(1 for x in a for y in b if y < x)
    return (naik - turun) / (len(a) * len(b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semua", action="store_true", help="ikutkan sesi yang tidak lengkap")
    ap.add_argument("--termasuk-uji", action="store_true", help="ikutkan anak uji (profil bertanda uji: true)")
    args = ap.parse_args()

    log = DATA / "log_langkah.jsonl"
    if not log.exists():
        print("Belum ada data: data/log_langkah.jsonl tidak ditemukan.")
        return 1

    terakhir: dict[tuple, dict] = {}
    tanpa_sesi = 0
    with open(log, encoding="utf-8") as f:
        for baris in f:
            r = json.loads(baris)
            if not r.get("sesi_id"):
                tanpa_sesi += 1
                continue
            terakhir[(r["sesi_id"], r["nomor_langkah"])] = r  # rekaman terakhir menang

    sesi: dict[str, dict] = {}
    for (sid, _), r in sorted(terakhir.items(), key=lambda kv: kv[1]["waktu"]):
        s = sesi.setdefault(sid, {"sesi_id": sid, "id_anak": r["id_anak"], "id_ta": r["id_ta"],
                                  "fase": r["fase"], "mulai": r["waktu"], "skor": {}})
        s["skor"][r["nomor_langkah"]] = r["skor"]

    profil = _profil()
    uji = {k for k, v in profil.items() if v.get("uji")}
    if uji and not args.termasuk_uji:
        sesi = {k: v for k, v in sesi.items() if v["id_anak"] not in uji}
    baris_sesi = []
    for s in sesi.values():
        level = profil.get(s["id_anak"], {}).get("level", "dasar")
        wajib = langkah_dinilai(s["id_ta"], level)
        nilai = [v for k, v in s["skor"].items() if k in wajib]
        lengkap = bool(wajib) and wajib <= set(s["skor"])
        pm = 100 * nilai.count("M") / len(wajib) if wajib else 0.0
        baris_sesi.append({"sesi_id": s["sesi_id"], "id_anak": s["id_anak"], "id_ta": s["id_ta"],
                           "fase": s["fase"], "mulai": s["mulai"], "M": nilai.count("M"),
                           "MB": nilai.count("MB"), "BM": nilai.count("BM"), "langkah_wajib": len(wajib),
                           "persen_mandiri": round(pm, 1), "lengkap": "ya" if lengkap else "tidak"})

    DATA.mkdir(exist_ok=True)
    kolom = ["sesi_id", "id_anak", "id_ta", "fase", "mulai", "M", "MB", "BM", "langkah_wajib",
             "persen_mandiri", "lengkap"]
    with open(DATA / "rekap_sesi.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        w.writerows(sorted(baris_sesi, key=lambda b: b["mulai"]))

    per = defaultdict(lambda: defaultdict(list))
    for b in sorted(baris_sesi, key=lambda b: b["mulai"]):
        if b["lengkap"] == "ya" or args.semua:
            per[(b["id_anak"], b["id_ta"])][b["fase"]].append(b["persen_mandiri"])

    ssr = []
    for (anak, ta), f in sorted(per.items()):
        a1, bb, a2 = f.get("A1", []), f.get("B", []), f.get("A2", [])
        rata = lambda xs: round(sum(xs) / len(xs), 1) if xs else ""
        p, t = pnd(a1, bb), tau_ab(a1, bb)
        ssr.append({"id_anak": anak, "id_ta": ta, "n_A1": len(a1), "rerata_A1": rata(a1),
                    "n_B": len(bb), "rerata_B": rata(bb), "n_A2": len(a2), "rerata_A2": rata(a2),
                    "PND_A1_B": "" if p is None else round(p, 1),
                    "Tau_A1_B": "" if t is None else round(t, 3)})
    with open(DATA / "rekap_ssr.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id_anak", "id_ta", "n_A1", "rerata_A1", "n_B", "rerata_B",
                                          "n_A2", "rerata_A2", "PND_A1_B", "Tau_A1_B"])
        w.writeheader()
        w.writerows(ssr)

    lengkap = sum(b["lengkap"] == "ya" for b in baris_sesi)
    print(f"Sesi: {len(baris_sesi)} ({lengkap} lengkap). Rekaman tanpa sesi_id dilewati: {tanpa_sesi}.")
    for r in ssr:
        print(f"  {r['id_anak']} {r['id_ta']}: A1 n={r['n_A1']} rerata={r['rerata_A1']} | "
              f"B n={r['n_B']} rerata={r['rerata_B']} | PND={r['PND_A1_B']} Tau={r['Tau_A1_B']}")
    print(f"Tersimpan: {DATA / 'rekap_sesi.csv'} dan {DATA / 'rekap_ssr.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
