"""Server MCP 'asd-rag' untuk Hermes Agent.

Tool:
  ambil_task_analysis  langkah dan ujaran persis dari korpus (pasti, bukan pencarian vektor)
  cari_strategi        pencarian semantik strategi (RAG)
  profil_anak          profil pseudonim anak
  catat_langkah        catat skor M/MB/BM per langkah untuk data SSR
  panggil_guru         eskalasi ke guru pendamping

Jalankan lewat Hermes (lihat hermes_config.yaml), atau uji manual:  python server.py
"""
from __future__ import annotations

import json
import os
import re
import threading
import secrets
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from korpus_lib import (DATA, FASE_SAH, MODE, SKOR_SAH, ambil_entri, isi_placeholder,
                        periksa_entri)

mcp = FastMCP("asd-rag")
LOG_SESI = DATA / "log_langkah.jsonl"
LOG_ESKALASI = DATA / "eskalasi.jsonl"
WEBHOOK = os.environ.get("ASD_RAG_WEBHOOK", "")   # mis. http://127.0.0.1:8765/internal/panggil_guru


def _token_webhook() -> str:
    """Token untuk webhook: ASD_RAG_WEBHOOK_TOKEN, atau token jembatan di data/.jembatan_token."""
    t = os.environ.get("ASD_RAG_WEBHOOK_TOKEN", "")
    p = DATA / ".jembatan_token"
    if not t and p.exists():
        t = p.read_text().strip()
    return t

ATURAN_PENYAMPAIAN = [
    "Ucapkan 'ujaran' persis seperti tertulis. Jangan menambah, mengganti, atau menggabungkan kata.",
    "Satu langkah per giliran. Tunggu respons anak sebelum langkah berikutnya.",
    "Jangan mengucapkan langkah dengan 'siap_diucapkan': false; panggil guru bila langkah itu diperlukan.",
    "Jika status regulasi kuning atau merah: hentikan, lalu jalankan TA-09.",
]


ZONA = ZoneInfo(os.environ.get("ASD_RAG_TZ", "Asia/Jakarta"))  # waktu log dalam WIB


def _sekarang() -> str:
    return datetime.now(ZONA).isoformat(timespec="seconds")


def _buat_sesi_id(id_anak: str, id_ta: str) -> str:
    return f"{_norm_id(id_anak)}-{_norm_id(id_ta)}-{datetime.now(ZONA):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def _norm_id(s: str) -> str:
    """'a-01', 'A 01', 'A01' dianggap sama."""
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


def _semua_profil() -> dict:
    path = DATA / "profil.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {_norm_id(k): v for k, v in json.load(f).items()}


def _profil(id_anak: str) -> dict | None:
    return _semua_profil().get(_norm_id(id_anak))


def _tulis(path, rekaman: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rekaman, ensure_ascii=False) + "\n")


@mcp.tool()
def ambil_task_analysis(id_ta: str, id_anak: str = "") -> dict:
    """Ambil task analysis tervalidasi berdasarkan kode (mis. 'TA-02') untuk anak tertentu.
    Placeholder seperti [pengering kelas] diisi dari profil anak. Ujaran wajib diucapkan persis.
    Setiap pemanggilan dengan id_anak membuka sesi baru dan mengembalikan 'sesi_id' yang WAJIB
    dipakai di setiap catat_langkah selama sesi tersebut."""
    d = ambil_entri("task_analysis", id_ta)
    if d is None:
        return {"error": f"{id_ta} tidak ditemukan atau belum berstatus valid (mode={MODE})."}
    galat, _ = periksa_entri(d)
    if galat:
        return {"error": f"{id_ta} gagal pemeriksaan aturan: {galat}"}

    profil = _profil(id_anak) if id_anak else None
    if id_anak and profil is None:
        return {"error": f"ID anak {id_anak} tidak ditemukan. Sesi tidak dibuka. Jangan menebak ID; tanyakan kepada guru."}
    isian = (profil or {}).get("isian", {})
    level_anak = (profil or {}).get("level", "dasar")
    urutan_level = {"dasar": 0, "menengah": 1, "lanjut": 2}

    langkah = []
    for s in d["langkah"]:
        ujaran, kosong = isi_placeholder(s["ujaran"], isian)
        item = {k: v for k, v in s.items() if k != "ujaran"}
        item["ujaran"] = ujaran
        item["kartu"], _ = isi_placeholder(s.get("kartu", ""), isian)
        item["siap_diucapkan"] = not kosong
        if kosong:
            item["placeholder_kosong"] = kosong
        lv = s.get("level_min")
        if lv and urutan_level.get(level_anak, 0) < urutan_level.get(lv, 0):
            item["aktif"] = False
            item["alasan_nonaktif"] = f"langkah untuk level {lv}; anak level {level_anak}"
        langkah.append(item)

    hasil = {
        "id": d["id"], "judul": d["judul"], "versi": d.get("versi"), "status": d["status"],
        "domain": d["domain"], "setting": d.get("setting"), "pemicu": d.get("pemicu"),
        "ulangi": d.get("ulangi"), "langkah": langkah, "catatan": d.get("catatan"),
        "aturan_penyampaian": ATURAN_PENYAMPAIAN,
    }
    if profil is not None:
        hasil["id_anak"] = _norm_id(id_anak)
        hasil["sesi_id"] = _buat_sesi_id(id_anak, d["id"])
        aktif = profil.get("ta_aktif")
        hasil["dalam_ta_aktif"] = True if aktif is None else _norm_id(d["id"]) in {_norm_id(x) for x in aktif}
    hasil = {k: v for k, v in hasil.items() if v is not None}
    if d["status"] != "valid":
        hasil["PERINGATAN"] = "Entri belum tervalidasi. Hanya untuk uji di profil pengembang, jangan dipakai ke anak."
    return hasil


MODE_CARI = os.environ.get("ASD_RAG_SEARCH", "hibrida")       # hibrida | semantik | kata
AMBANG_SEM = float(os.environ.get("ASD_RAG_T_SEM", "0.5"))     # dikalibrasi dengan eval_retrieval.py
AMBANG_KATA = float(os.environ.get("ASD_RAG_T_KATA", "0.15"))
_cache: dict = {}
_kunci = threading.Lock()


def _sumber_cari():
    """Muat sekali: koleksi Chroma, embedder, dan indeks kata untuk entri yang berlaku di mode ini."""
    with _kunci:
        return _muat_sumber()


def _muat_sumber():
    if "kol" not in _cache:
        import chromadb
        from korpus_lib import Embedder, Leksikal, semua_entri

        kol = chromadb.PersistentClient(path=str(DATA / "chroma")).get_collection("korpus_asd")
        emb = Embedder()
        if kol.metadata.get("embedder") != emb.nama or kol.metadata.get("skema") != "potongan-v1":
            raise RuntimeError(f"Indeks tidak cocok (embedder {kol.metadata.get('embedder')}, "
                               f"skema {kol.metadata.get('skema')}). Jalankan ulang ingest.py.")
        entri = {d["id"]: d for d in semua_entri("strategi") + semua_entri("task_analysis")}
        _cache.update(kol=kol, emb=emb, entri=entri, leks=Leksikal(list(entri.values())))
    return _cache["kol"], _cache["emb"], _cache["entri"], _cache["leks"]


@mcp.tool()
def cari_strategi(pertanyaan: str, domain: str = "", k: int = 3) -> dict:
    """Cari strategi atau task analysis yang relevan dengan pertanyaan guru (pencarian hibrida:
    semantik + kecocokan kata). domain opsional: kemandirian, komunikasi, sosial, regulasi sensori,
    akademik. Gunakan hasil hanya sebagai rujukan; selalu sebutkan id dan rujukannya. Jika
    'relevan' bernilai false untuk semua hasil, katakan bahwa korpus tidak memuat jawabannya."""
    from korpus_lib import susun_peringkat

    try:
        kol, emb, entri, leks = _sumber_cari()
    except Exception as e:
        return {"error": f"Indeks belum siap: {e}. Jalankan: python ingest.py"}
    if domain:
        entri = {i: d for i, d in entri.items() if d.get("domain") == domain}
        if not entri:
            return {"error": f"Tidak ada entri untuk domain '{domain}'."}

    r = kol.query(query_embeddings=emb([pertanyaan]), n_results=kol.count())
    sem: dict[str, float] = {}
    for m, jarak in zip(r["metadatas"][0], r["distances"][0]):
        if m["entri"] in entri:
            sem[m["entri"]] = max(sem.get(m["entri"], -1.0), 1 - jarak)
    kata = {i: s for i, s in leks.skor(pertanyaan).items() if i in entri}

    k = max(1, min(int(k), 5))
    hasil = []
    for i in susun_peringkat(sem, kata, MODE_CARI)[:k]:
        d = entri[i]
        s, w = round(sem.get(i, 0.0), 3), round(kata.get(i, 0.0), 3)
        hasil.append({"id": i, "jenis": d["jenis"], "judul": d["judul"], "status": d["status"],
                      "kemiripan_semantik": s, "kemiripan_kata": w,
                      "relevan": s >= AMBANG_SEM or w >= AMBANG_KATA,
                      "isi": d.get("isi") or d.get("catatan"),
                      "langkah_tutor": d.get("langkah_tutor"), "rujukan": d.get("rujukan")})
    return {"pertanyaan": pertanyaan, "mode": MODE_CARI, "hasil": hasil}


@mcp.tool()
def profil_anak(id_anak: str) -> dict:
    """Ambil profil belajar anak berdasarkan ID pseudonim (mis. 'A01'). Tidak memuat nama asli."""
    p = _profil(id_anak)
    if p is not None:
        return {"id_anak": _norm_id(id_anak), **p}
    hasil = {"error": f"ID {id_anak} tidak ditemukan. Jangan menebak ID; tanyakan kepada guru."}
    if MODE == "dev":
        hasil["id_tersedia"] = sorted(_semua_profil())
    return hasil


@mcp.tool()
def catat_langkah(sesi_id: str, id_anak: str, id_ta: str, nomor_langkah: int, skor: str,
                  fase: str = "B", catatan: str = "") -> dict:
    """Catat hasil satu langkah untuk data SSR.
    sesi_id: dari hasil ambil_task_analysis sesi yang sedang berjalan (wajib).
    skor: M (mampu mandiri), MB (mampu dengan bantuan), BM (belum mampu).
    fase: A1 (baseline), B (intervensi), A2 (baseline akhir)."""
    skor, fase = skor.upper().strip(), fase.upper().strip()
    if not sesi_id or not sesi_id.startswith(_norm_id(id_anak) + "-"):
        return {"error": "sesi_id wajib dan harus berasal dari ambil_task_analysis untuk anak ini."}
    if skor not in SKOR_SAH:
        return {"error": f"skor harus salah satu dari {sorted(SKOR_SAH)}"}
    if fase not in FASE_SAH:
        return {"error": f"fase harus salah satu dari {sorted(FASE_SAH)}"}
    d = ambil_entri("task_analysis", id_ta)
    if d is None:
        return {"error": f"{id_ta} tidak ditemukan."}
    if not 1 <= int(nomor_langkah) <= len(d["langkah"]):
        return {"error": f"{id_ta} hanya punya {len(d['langkah'])} langkah."}
    rekaman = {"waktu": _sekarang(), "sesi_id": sesi_id, "id_anak": _norm_id(id_anak), "id_ta": d["id"], "versi_ta": d.get("versi"),
               "nomor_langkah": int(nomor_langkah), "skor": skor, "fase": fase, "catatan": catatan}
    _tulis(LOG_SESI, rekaman)
    return {"status": "tersimpan", **rekaman}


@mcp.tool()
def panggil_guru(id_anak: str, alasan: str, tingkat: str = "sedang") -> dict:
    """Panggil guru pendamping. Wajib dipakai untuk: distres yang bertahan, indikasi bahaya/sakit,
    tiga kali keliru berturut-turut, atau anak menolak. tingkat: rendah, sedang, tinggi."""
    rekaman = {"waktu": _sekarang(), "id_anak": _norm_id(id_anak), "alasan": alasan, "tingkat": tingkat}
    _tulis(LOG_ESKALASI, rekaman)
    terkirim = False
    if WEBHOOK:
        try:
            kepala = {"Content-Type": "application/json"}
            if _token_webhook():
                kepala["Authorization"] = f"Bearer {_token_webhook()}"
            req = urllib.request.Request(WEBHOOK, data=json.dumps(rekaman).encode(), headers=kepala)
            with urllib.request.urlopen(req, timeout=3) as jawab:
                terkirim = 200 <= jawab.status < 300
        except Exception as e:  # jangan gagalkan eskalasi karena webhook
            rekaman["webhook_error"] = str(e)
    return {"status": "guru dipanggil", "webhook_terkirim": terkirim,
            "instruksi_tutor": "Hentikan materi. Jangan mengulang instruksi. Tunggu guru mengambil alih."}


def _pemanasan():
    """Muat model embedding di latar belakang agar panggilan cari_strategi pertama tidak lambat."""
    try:
        _sumber_cari()
    except Exception:
        pass  # galat akan dilaporkan saat cari_strategi dipanggil


if __name__ == "__main__":
    # Model embedding (~1 GB) hanya dimuat saat cari_strategi pertama kali dipanggil, kecuali
    # ASD_RAG_PEMANASAN=1. Tutor tidak memakai cari_strategi, jadi di server RAM 2 GB model tidak ikut dimuat.
    if os.environ.get("ASD_RAG_PEMANASAN") == "1":
        threading.Thread(target=_pemanasan, daemon=True).start()
    mcp.run()
