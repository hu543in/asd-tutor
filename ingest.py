"""Bangun indeks vektor untuk pencarian strategi (dan ringkasan task analysis).

Task analysis TIDAK diambil dari indeks ini saat sesi dengan anak: tutor memanggil
ambil_task_analysis(id) yang membaca file YAML secara pasti. Indeks ini hanya untuk
cari_strategi(), mis. pertanyaan guru "anak sulit berpindah aktivitas".

Setiap entri dipecah menjadi potongan pendek (inti, isi, langkah) agar makna utamanya
tidak kabur; skor entri = skor potongan tertinggi.

Pemakaian:
  python ingest.py                    # mode prod: hanya entri status 'valid'
  ASD_RAG_MODE=dev python ingest.py   # uji: entri draft ikut diindeks
"""
import sys

import chromadb

from korpus_lib import DATA, MODE, Embedder, periksa_entri, potongan_entri, semua_entri

KOLEKSI = "korpus_asd"


def main() -> int:
    entri = semua_entri("strategi") + semua_entri("task_analysis")
    if not entri:
        print(f"Tidak ada entri untuk diindeks (mode={MODE}). Di mode prod hanya status 'valid' yang dimuat.")
        return 1

    lolos = []
    for d in entri:
        galat, _ = periksa_entri(d)
        if galat:
            print(f"DILEWATI {d['id']}: {galat[0]}")
            continue
        lolos.append(d)

    ids, teks, meta = [], [], []
    for d in lolos:
        for bagian, t in potongan_entri(d):
            ids.append(f"{d['id']}#{bagian}")
            teks.append(t)
            meta.append({"entri": d["id"], "bagian": bagian, "jenis": d["jenis"], "domain": d["domain"],
                         "level": d["level"], "status": d["status"], "judul": d["judul"]})

    emb = Embedder()
    klien = chromadb.PersistentClient(path=str(DATA / "chroma"))
    try:
        klien.delete_collection(KOLEKSI)
    except Exception:
        pass
    kol = klien.create_collection(KOLEKSI, metadata={
        "hnsw:space": "cosine", "embedder": emb.nama, "mode": MODE, "skema": "potongan-v1"})
    kol.add(ids=ids, documents=teks, embeddings=emb(teks), metadatas=meta)
    print(f"Selesai: {len(lolos)} entri ({len(ids)} potongan) diindeks (mode={MODE}, embedder={emb.nama}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
