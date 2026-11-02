"""Evaluasi pencarian: bandingkan model embedding, chunking, dan mode pencarian.

Metrik: Recall@1, Recall@3 (minimal satu jawaban benar di 3 teratas), MRR.
Kueri negatif (di luar cakupan korpus) dipakai untuk mengkalibrasi ambang 'relevan'.

Pemakaian (di server, dari folder asd-rag):
  ASD_RAG_MODE=dev ./venv/bin/python eval_retrieval.py
  ASD_RAG_MODE=dev ./venv/bin/python eval_retrieval.py --model minilm      # satu model saja

Hasil disimpan ke data/eval_retrieval.csv.

PENTING untuk disertasi: kueri di bawah ini ditulis oleh pengembang. Untuk evaluasi akhir,
tambahkan kueri yang ditulis guru/validator agar tidak bias terhadap kosakata korpus.
"""
from __future__ import annotations

import argparse
import csv
import math
import os

from korpus_lib import DATA, Leksikal, potongan_entri, semua_entri, susun_peringkat, teks_untuk_indeks

KUERI = [
    ("anak sulit berpindah aktivitas", {"TA-08", "STR-SEN-001"}),
    ("anak tantrum ketika jadwal berubah mendadak", {"STR-SEN-001", "TA-08"}),
    ("bagaimana mengajarkan anak mencuci tangan", {"TA-02"}),
    ("anak tidak mau minta tolong saat kesulitan", {"TA-06"}),
    ("melatih anak menunggu giliran saat bermain", {"TA-07"}),
    ("anak gelisah dan perlu menenangkan diri", {"TA-09"}),
    ("anak marah dan menangis di kelas", {"TA-09"}),
    ("mengenalkan konsep jumlah benda dan angka", {"TA-10"}),
    ("anak belum bisa berhitung satu per satu", {"TA-10"}),
    ("rutinitas pagi saat anak datang ke sekolah", {"TA-01"}),
    ("anak menaruh tas di tempatnya", {"TA-01"}),
    ("latihan makan sendiri di jam istirahat", {"TA-03"}),
    ("merapikan pensil dan alat tulis setelah belajar", {"TA-04"}),
    ("anak belum mau memberi salam kepada guru", {"TA-05"}),
    ("cara bicara kepada anak agar instruksi mudah dipahami", {"STR-KOM-001"}),
    ("anak butuh waktu lama untuk merespons instruksi", {"STR-KOM-001"}),
]
NEGATIF = [
    "cara menurunkan demam anak",
    "jadwal imunisasi untuk anak usia sekolah",
    "biaya pendaftaran sekolah luar biasa",
    "resep nasi goreng untuk bekal",
]
MODEL = {
    "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "mpnet": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
}


def _cos(a, b):
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def skor_semantik(emb, entri, chunk: bool):
    """Kembalikan fungsi kueri -> {id: skor} untuk satu konfigurasi."""
    unit = []  # (id_entri, teks)
    for d in entri:
        if chunk:
            unit += [(d["id"], t) for _, t in potongan_entri(d)]
        else:
            unit.append((d["id"], teks_untuk_indeks(d)))
    vek = emb([t for _, t in unit])

    def f(q: str) -> dict[str, float]:
        qv = emb([q])[0]
        s: dict[str, float] = {}
        for (i, _), v in zip(unit, vek):
            s[i] = max(s.get(i, -1.0), _cos(qv, v))
        return s
    return f


def evaluasi(peringkat_fn):
    r1 = r3 = rr = 0.0
    for q, benar in KUERI:
        urut = peringkat_fn(q)
        pos = next((n for n, i in enumerate(urut, 1) if i in benar), None)
        r1 += pos == 1
        r3 += pos is not None and pos <= 3
        rr += 1 / pos if pos else 0
    n = len(KUERI)
    return r1 / n, r3 / n, rr / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(MODEL), nargs="*", default=list(MODEL))
    args = ap.parse_args()

    entri = semua_entri("strategi") + semua_entri("task_analysis")
    if not entri:
        raise SystemExit("Korpus kosong. Jalankan dengan ASD_RAG_MODE=dev untuk korpus draft.")
    leks = Leksikal(entri)
    baris = []

    r = evaluasi(lambda q: susun_peringkat({}, leks.skor(q), "kata"))
    baris.append(("-", "-", "kata", *r))

    for nama in args.model:
        os.environ["ASD_RAG_EMBED_MODEL"] = MODEL[nama]
        from korpus_lib import Embedder
        print(f"Memuat model {nama} ...")
        emb = Embedder()
        label = nama if emb.jenis == "fastembed" else "hash"
        for chunk in (False, True):
            sem_fn = skor_semantik(emb, entri, chunk)
            for mode in ("semantik", "hibrida"):
                r = evaluasi(lambda q: susun_peringkat(sem_fn(q), leks.skor(q), mode))
                baris.append((label, "ya" if chunk else "tidak", mode, *r))
            # kalibrasi ambang dari kueri negatif (konfigurasi berpotongan)
            if chunk:
                neg_sem = max(max(sem_fn(q).values()) for q in NEGATIF)
                pos_sem = sorted(max(sem_fn(q)[i] for i in b) for q, b in KUERI)
                print(f"  [{label}] semantik: skor tertinggi kueri negatif = {neg_sem:.3f}; "
                      f"skor jawaban benar terendah = {pos_sem[0]:.3f}, median = {pos_sem[len(pos_sem)//2]:.3f}")
    neg_kata = max(max(leks.skor(q).values()) for q in NEGATIF)
    print(f"  [kata] skor tertinggi kueri negatif = {neg_kata:.3f}")

    print(f"\n{'Model':8} {'Chunk':6} {'Mode':9} {'R@1':>5} {'R@3':>5} {'MRR':>5}")
    for m, c, mode, r1, r3, mrr in baris:
        print(f"{m:8} {c:6} {mode:9} {r1:5.2f} {r3:5.2f} {mrr:5.2f}")

    DATA.mkdir(exist_ok=True)
    with open(DATA / "eval_retrieval.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "chunking", "mode", "recall_at_1", "recall_at_3", "mrr", "n_kueri"])
        for b in baris:
            w.writerow([*b[:3], *(round(x, 3) for x in b[3:]), len(KUERI)])
    print(f"\nTersimpan: {DATA / 'eval_retrieval.csv'}")
    print("Saran ambang: ASD_RAG_T_SEM sedikit di atas skor negatif semantik, "
          "ASD_RAG_T_KATA sedikit di atas skor negatif kata.")


if __name__ == "__main__":
    main()
