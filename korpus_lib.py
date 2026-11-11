"""Pustaka bersama: memuat korpus, memeriksa aturan, mengisi placeholder, embedding.

Variabel lingkungan:
  ASD_RAG_HOME         folder proyek (default: folder file ini)
  ASD_RAG_MODE         "prod" (default, hanya entri status valid) atau "dev" (draft ikut dimuat)
  ASD_RAG_EMBED        "fastembed" (default) atau "hash" (uji offline tanpa unduh model)
  ASD_RAG_EMBED_MODEL  default "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from pathlib import Path

import yaml

HOME = Path(os.environ.get("ASD_RAG_HOME", Path(__file__).resolve().parent))
KORPUS = HOME / "korpus"
DATA = HOME / "data"
MODE = os.environ.get("ASD_RAG_MODE", "prod").lower()
STATUS_SAH = {"draft", "review", "valid"}
SKOR_SAH = {"M", "MB", "BM"}
FASE_SAH = {"A1", "B", "A2"}

PLACEHOLDER = re.compile(r"\[([^\]]+)\]")
MAKS_KATA = 8
KATA_NEGATIF = {"salah", "bukan", "jangan", "tidak boleh"}


# ---------- memuat korpus ----------
def _baca(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def semua_entri(jenis: str, termasuk_draft: bool | None = None) -> list[dict]:
    """Kembalikan entri satu jenis ('task_analysis' atau 'strategi').

    Mode prod hanya mengembalikan entri berstatus 'valid'."""
    if termasuk_draft is None:
        termasuk_draft = MODE == "dev"
    folder = KORPUS / jenis
    hasil = []
    for p in sorted(folder.glob("*.yaml")):
        d = _baca(p)
        d["_file"] = p.name
        if d.get("status") == "valid" or termasuk_draft:
            hasil.append(d)
    return hasil


def ambil_entri(jenis: str, id_entri: str) -> dict | None:
    for d in semua_entri(jenis):
        if re.sub(r"[^A-Z0-9]", "", d.get("id", "").upper()) == re.sub(r"[^A-Z0-9]", "", id_entri.upper()):
            return d
    return None


# ---------- pemeriksaan aturan ----------
def hitung_kata(ujaran: str) -> int:
    teks = PLACEHOLDER.sub("X", ujaran)  # satu placeholder = satu kata
    return len(re.findall(r"[\wÀ-ÿ'-]+", teks))


def periksa_entri(d: dict) -> tuple[list[str], list[str]]:
    """Kembalikan (galat, peringatan). Galat menghalangi ingest."""
    galat, peringatan = [], []
    wajib = ("id", "jenis", "status", "judul") if d.get("jenis") == "bank_ujaran" else \
        ("id", "jenis", "status", "judul", "domain", "level")
    for k in wajib:
        if not d.get(k):
            galat.append(f"kolom '{k}' kosong")
    if d.get("status") not in STATUS_SAH:
        galat.append(f"status '{d.get('status')}' tidak dikenal")
    if d.get("status") == "valid":
        v = d.get("validasi") or {}
        if not v.get("validator") or v.get("aiken_v") is None:
            galat.append("status valid tetapi data validasi (validator, aiken_v) kosong")
    if d.get("jenis") == "task_analysis":
        langkah = d.get("langkah") or []
        if not langkah:
            galat.append("tidak ada langkah")
        for i, s in enumerate(langkah, 1):
            if s.get("nomor") != i:
                galat.append(f"nomor langkah ke-{i} tertulis {s.get('nomor')}")
            uj = s.get("ujaran", "")
            if not uj:
                galat.append(f"langkah {i}: ujaran kosong")
                continue
            n = hitung_kata(uj)
            if n > MAKS_KATA:
                galat.append(f"langkah {i}: ujaran {n} kata (maks {MAKS_KATA}): {uj}")
            low = f" {uj.lower()} "
            if " atau " in low:
                galat.append(f"langkah {i}: ujaran berisi pilihan 'atau': {uj}")
            for neg in KATA_NEGATIF:
                if f" {neg} " in re.sub(r"[^\w\s]", " ", low):
                    peringatan.append(f"langkah {i}: ujaran memuat kata negatif '{neg}': {uj}")
            if re.search(r"\b(dan|lalu|kemudian)\b", uj.lower()):
                peringatan.append(f"langkah {i}: periksa apakah ujaran berisi dua tindakan: {uj}")
    if d.get("jenis") == "bank_ujaran":
        daftar = d.get("ujaran") or []
        if not daftar:
            galat.append("bank tidak berisi ujaran")
        dilihat = set()
        for u in daftar:
            uid, uj = u.get("id", "?"), u.get("ujaran", "")
            if uid in dilihat:
                galat.append(f"{uid}: ID ganda")
            dilihat.add(uid)
            if u.get("status", "valid") not in ("valid", "ditolak"):
                galat.append(f"{uid}: status ujaran '{u.get('status')}' tidak dikenal (valid/ditolak)")
            if not uj:
                galat.append(f"{uid}: ujaran kosong")
                continue
            if hitung_kata(uj) > MAKS_KATA:
                galat.append(f"{uid}: ujaran lebih dari {MAKS_KATA} kata: {uj}")
            low = re.sub(r"[^\w\s]", " ", f" {uj.lower()} ")
            if " atau " in low:
                galat.append(f"{uid}: ujaran berisi pilihan 'atau': {uj}")
            for neg in KATA_NEGATIF:
                if f" {neg} " in low:
                    peringatan.append(f"{uid}: ujaran memuat kata negatif '{neg}': {uj}")
    return galat, peringatan


# ---------- placeholder ----------
def isi_placeholder(teks: str, isian: dict) -> tuple[str, list[str]]:
    kosong = []

    def ganti(m):
        kunci = m.group(1).strip()
        if kunci in isian and isian[kunci]:
            return str(isian[kunci])
        kosong.append(kunci)
        return m.group(0)

    return PLACEHOLDER.sub(ganti, teks), kosong


# ---------- embedding ----------
class Embedder:
    """fastembed (model multibahasa, ONNX, tanpa torch) atau hash n-gram untuk uji offline."""

    def __init__(self):
        self.jenis = os.environ.get("ASD_RAG_EMBED", "fastembed").lower()
        self.model_name = os.environ.get(
            "ASD_RAG_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        self._model = None
        if self.jenis == "fastembed":
            from fastembed import TextEmbedding
            self._model = TextEmbedding(self.model_name, cache_dir=str(HOME / "models"))

    @property
    def nama(self) -> str:
        return self.model_name if self.jenis == "fastembed" else "hash-trigram-512"

    def __call__(self, teks: list[str]) -> list[list[float]]:
        if self._model is not None:
            return [list(map(float, v)) for v in self._model.embed(teks)]
        return [self._hash(t) for t in teks]

    @staticmethod
    def _hash(t: str, dim: int = 512) -> list[float]:
        t = f"  {t.lower()}  "
        v = [0.0] * dim
        for i in range(len(t) - 2):
            h = int(hashlib.md5(t[i:i + 3].encode()).hexdigest(), 16)
            v[h % dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


def teks_untuk_indeks(d: dict) -> str:
    """Seluruh teks satu entri (dipakai untuk skor kecocokan kata)."""
    return ". ".join(t for _, t in potongan_entri(d))


def potongan_entri(d: dict) -> list[tuple[str, str]]:
    """Pecah entri menjadi potongan pendek agar makna utama tidak kabur (chunking).

    Kembalikan daftar (nama_bagian, teks)."""
    hasil = []
    inti = ". ".join(x for x in [d.get("judul", ""), d.get("pemicu", ""), d.get("kapan_dipakai", "")] if x)
    hasil.append(("inti", inti))
    isi = d.get("isi") or d.get("catatan") or ""
    if isi:
        hasil.append(("isi", isi))
    langkah = [s.get("tindakan", "") for s in d.get("langkah", []) or []]
    langkah += [s for s in d.get("langkah_tutor", []) or [] if isinstance(s, str)]
    if langkah:
        hasil.append(("langkah", ". ".join(langkah)))
    return hasil


# ---------- skor kecocokan kata (leksikal) ----------
def _trigram(teks: str) -> Counter:
    c = Counter()
    for kata in re.findall(r"\w+", teks.lower()):
        k = f" {kata} "
        for i in range(len(k) - 2):
            c[k[i:i + 3]] += 1
    return c


class Leksikal:
    """TF-IDF trigram karakter: tahan imbuhan bahasa Indonesia (pindah ~ berpindah)."""

    def __init__(self, entri: list[dict]):
        self.ids = [d["id"] for d in entri]
        dokumen = []
        for d in entri:
            # judul diberi bobot ganda karena paling menentukan topik
            dokumen.append(_trigram(d.get("judul", "") + " " + d.get("judul", "") + " " + teks_untuk_indeks(d)))
        n = len(dokumen)
        df = Counter(t for doc in dokumen for t in doc)
        self.idf = {t: math.log((n + 1) / (f + 1)) + 1 for t, f in df.items()}
        self.vek = [self._bobot(doc) for doc in dokumen]

    def _bobot(self, c: Counter) -> dict:
        v = {t: (1 + math.log(f)) * self.idf.get(t, 0.0) for t, f in c.items()}
        n = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / n for t, x in v.items()}

    def skor(self, kueri: str) -> dict[str, float]:
        q = self._bobot(_trigram(kueri))
        return {i: sum(w * v.get(t, 0.0) for t, w in q.items()) for i, v in zip(self.ids, self.vek)}


def susun_peringkat(sem: dict[str, float], kata: dict[str, float], mode: str = "hibrida") -> list[str]:
    """Urutkan id entri. mode: 'semantik', 'kata', atau 'hibrida' (RRF)."""
    urut_sem = sorted(sem, key=sem.get, reverse=True)
    urut_kata = sorted(kata, key=kata.get, reverse=True)
    if mode == "semantik":
        return urut_sem
    if mode == "kata":
        return urut_kata
    gab = gabung_rrf(urut_sem, urut_kata)
    return sorted(gab, key=gab.get, reverse=True)


def gabung_rrf(*peringkat: list[str], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion: gabungkan beberapa daftar peringkat tanpa perlu menyamakan skala skor."""
    skor: dict[str, float] = {}
    for daftar in peringkat:
        for r, i in enumerate(daftar, 1):
            skor[i] = skor.get(i, 0.0) + 1.0 / (k + r)
    return skor
