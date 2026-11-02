"""Jembatan metaverse (Langkah 8): WebSocket antara metaverse, tutor Hermes, dan guru.

  metaverse ──ws /ws/metaverse──┐                ┌── Hermes profil tutor-asd (API server)
                                ├── jembatan ────┤
  dasbor guru ──ws /ws/guru─────┘   │            └── penjaga.py (setiap jawaban)
                                    └── data/jembatan.jsonl (log giliran)

Aturan yang dijaga jembatan:
  - Setiap jawaban tutor melewati penjaga; metaverse hanya menerima `keluaran` yang aman,
    tanpa `catatan_guru`.
  - Teks dari anak dibersihkan dari tanda [ ] { } agar tidak bisa meniru perintah [GURU] atau [SISTEM].
  - Satu giliran pada satu waktu per anak; pesan berikutnya antre.
  - Tombol HENTIKAN guru langsung membuat avatar diam; jawaban tutor yang datang terlambat dibuang.
  - Mode dev hanya menerima profil anak bertanda "uji": true.

Jalankan (di server):
  ./venv/bin/python jembatan.py              # penggerak API Hermes, 127.0.0.1:8765
  JEMBATAN_PENGGERAK=palsu ./venv/bin/python jembatan.py   # tanpa Hermes, untuk mencoba dasbor
Lalu buka http://127.0.0.1:8765/guru lewat terowongan SSH (lihat README).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import WSMsgType, web

from hermes_klien import TOOL_META_MCP, buat_klien
from korpus_lib import DATA, FASE_SAH, MODE, periksa_entri, semua_entri
from penjaga import Penjaga, norm_id

SINI = Path(__file__).resolve().parent
ZONA = ZoneInfo(os.environ.get("ASD_RAG_TZ", "Asia/Jakarta"))
LOG = DATA / "jembatan.jsonl"
BATAS_WAKTU = float(os.environ.get("JEMBATAN_BATAS_WAKTU", "120"))
PERINTAH_GURU = {"SETUJU", "LANJUT", "SELESAI"}
RESPONS = {"benar", "keliru", "tidak_ada"}
REGULASI = {"kuning", "merah"}
KOLOM_METAVERSE = ("pujian", "ucap", "kartu", "aksi", "ta", "langkah")
BERKAS_LATAR = SINI / "static" / "aset" / "latar" / "latar.json"


def sekarang() -> str:
    return datetime.now(ZONA).isoformat(timespec="seconds")


def bersihkan_teks_anak(t: str) -> str:
    t = re.sub(r"[\[\]{}<>\x00-\x1f\x7f]", " ", str(t or ""))
    return re.sub(r"\s+", " ", t).strip()[:200]


def tulis_log(rekaman: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rekaman, ensure_ascii=False) + "\n")


def token_jembatan() -> str:
    t = os.environ.get("JEMBATAN_TOKEN")
    if t:
        return t
    p = DATA / ".jembatan_token"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_urlsafe(18))
        p.chmod(0o600)
    return p.read_text().strip()


def muat_latar(p: Path = BERKAS_LATAR) -> dict:
    """Daftar latar ruangan dan peta TA -> latar dari latar.json. Tanpa berkas: tidak ada latar (klien
    memakai ruang kelas cadangannya)."""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        latar = {k: str(v.get("nama", k)) for k, v in d.get("latar", {}).items()}
        peta = {k: v for k, v in d.get("peta_ta", {}).items() if v in latar}
        bawaan = d.get("bawaan") if d.get("bawaan") in latar else next(iter(latar), None)
        return {"latar": latar, "peta_ta": peta, "bawaan": bawaan}
    except Exception:
        return {"latar": {}, "peta_ta": {}, "bawaan": None}


def muat_profil() -> dict:
    p = DATA / "profil.json"
    if not p.exists():
        return {}
    return {norm_id(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items()}


class Ruang:
    """Satu anak, satu guru, satu (atau lebih) klien metaverse."""

    def __init__(self, id_anak: str):
        self.id_anak = id_anak
        self.guru: set[web.WebSocketResponse] = set()
        self.metaverse: set[web.WebSocketResponse] = set()
        self.percakapan: str | None = None
        self.ta = self.fase = None
        self.jeda = False
        self.epoch = 0             # naik setiap MULAI/HENTIKAN; jawaban dari epoch lama dibuang
        self.alasan_epoch = ""
        self.giliran = 0
        self.kunci = asyncio.Lock()
        self.riwayat: deque = deque(maxlen=200)
        self.berpikir = False
        self.terakhir_tool_panggil = -1e9   # waktu panggil_guru terakhir yang datang langsung dari tool
        self.latar_pilihan: str | None = None   # pilihan guru; None = otomatis mengikuti TA
        self.latar: str | None = None           # latar yang sedang tampil di metaverse

    async def kirim(self, sasaran: set, pesan: dict) -> None:
        for ws in list(sasaran):
            try:
                await ws.send_json(pesan)
            except Exception:
                sasaran.discard(ws)

    async def ke_guru(self, pesan: dict, simpan: bool = True) -> None:
        pesan = {"waktu": sekarang(), **pesan}
        if simpan:
            self.riwayat.append(pesan)
        await self.kirim(self.guru, pesan)

    async def ke_metaverse(self, pesan: dict) -> None:
        await self.kirim(self.metaverse, pesan)

    def status(self) -> dict:
        return {"tipe": "status", "id_anak": self.id_anak, "sesi_aktif": self.percakapan is not None,
                "ta": self.ta, "fase": self.fase, "jeda": self.jeda, "berpikir": self.berpikir,
                "metaverse_terhubung": len(self.metaverse), "guru_terhubung": len(self.guru),
                "latar": self.latar, "latar_pilihan": self.latar_pilihan or "otomatis"}


class Jembatan:
    def __init__(self, klien=None, penjaga: Penjaga | None = None, token: str | None = None,
                 mode: str | None = None):
        self.mode = (mode or MODE).lower()
        self.klien = klien or buat_klien()
        self.penjaga = penjaga or Penjaga(mode=self.mode, eskalasi=True)
        self.token = token or token_jembatan()
        self.ruang: dict[str, Ruang] = {}
        self.profil = muat_profil()
        self.latar = muat_latar()
        draft = self.mode == "dev"
        self.daftar_ta = [{"id": d["id"], "judul": d["judul"]}
                          for d in semua_entri("task_analysis", termasuk_draft=draft) if not periksa_entri(d)[0]]

    # ---------- latar ruangan ----------
    def latar_untuk(self, r: Ruang) -> str | None:
        if r.latar_pilihan:
            return r.latar_pilihan
        peta = {norm_id(k): v for k, v in self.latar["peta_ta"].items()}
        return peta.get(norm_id(r.ta or ""), self.latar["bawaan"])

    async def terapkan_latar(self, r: Ruang, sebab: str) -> None:
        baru = self.latar_untuk(r)
        if not baru or baru == r.latar:
            return
        r.latar = baru
        await r.ke_metaverse({"tipe": "latar", "nilai": baru})
        await r.ke_guru({"tipe": "info", "pesan": f"Latar: {self.latar['latar'][baru]} ({sebab})."})
        tulis_log({"waktu": sekarang(), "id_anak": r.id_anak, "percakapan": r.percakapan, "acara": "latar",
                   "latar": baru, "sebab": sebab, "ta": r.ta})

    # ---------- akses ----------
    def _token_sah(self, req: web.Request) -> bool:
        t = req.query.get("token") or req.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        return bool(t) and secrets.compare_digest(t, self.token)

    def anak_diizinkan(self, id_anak: str) -> tuple[bool, str]:
        p = self.profil.get(norm_id(id_anak))
        if p is None:
            return False, f"ID anak {id_anak} tidak ada di profil.json"
        if self.mode == "dev" and not p.get("uji"):
            return False, "mode dev hanya untuk profil uji (\"uji\": true); anak nyata hanya di mode prod"
        return True, ""

    def ambil_ruang(self, id_anak: str) -> Ruang:
        k = norm_id(id_anak)
        if k not in self.ruang:
            self.ruang[k] = Ruang(k)
        return self.ruang[k]

    # ---------- HTTP ----------
    async def halaman_guru(self, req):
        return web.FileResponse(SINI / "static" / "guru.html")

    async def halaman_metaverse(self, req):
        """Klien metaverse A-Frame. Halaman sendiri tidak memuat data; WebSocket-nya tetap butuh token."""
        return web.FileResponse(SINI / "static" / "metaverse.html")

    async def internal_panggil_guru(self, req):
        """Dipanggil tool panggil_guru di server MCP (ASD_RAG_WEBHOOK). Hanya dari server ini sendiri:
        ditolak bila lewat Caddy (ada X-Forwarded-For) atau tanpa token jembatan."""
        if req.headers.get("X-Forwarded-For") or req.remote not in ("127.0.0.1", "::1"):
            return web.json_response({"error": "hanya untuk proses di server ini"}, status=403)
        if not self._token_sah(req):
            return web.json_response({"error": "token salah"}, status=401)
        try:
            d = await req.json()
            assert isinstance(d, dict)
        except Exception:
            return web.json_response({"error": "isi harus objek JSON"}, status=400)
        id_anak = norm_id(str(d.get("id_anak", "")))
        if id_anak not in self.profil:
            return web.json_response({"error": f"ID anak {id_anak} tidak dikenal"}, status=404)
        tingkat = str(d.get("tingkat", "sedang")).lower()
        tingkat = tingkat if tingkat in {"rendah", "sedang", "tinggi"} else "sedang"
        alasan = str(d.get("alasan", ""))[:500]
        r = self.ambil_ruang(id_anak)
        r.terakhir_tool_panggil = time.monotonic()
        await r.ke_guru({"tipe": "panggil_guru", "sumber": "tool", "tingkat": tingkat, "alasan": alasan})
        tulis_log({"waktu": sekarang(), "id_anak": id_anak, "percakapan": r.percakapan,
                   "acara": "panggil_guru", "tingkat": tingkat, "alasan": alasan})
        return web.json_response({"diterima": True, "guru_terhubung": len(r.guru)})

    async def info(self, req):
        if not self._token_sah(req):
            return web.json_response({"error": "token salah"}, status=401)
        anak = [k for k, v in self.profil.items() if self.mode != "dev" or v.get("uji")]
        return web.json_response({"mode": self.mode, "penggerak": self.klien.nama, "anak": sorted(anak),
                                  "ta": self.daftar_ta, "fase": sorted(FASE_SAH),
                                  "latar": [{"id": k, "nama": v} for k, v in self.latar["latar"].items()],
                                  "peta_latar": self.latar["peta_ta"]})

    # ---------- WebSocket ----------
    async def ws_guru(self, req):
        return await self._ws(req, "guru")

    async def ws_metaverse(self, req):
        return await self._ws(req, "metaverse")

    async def _ws(self, req, peran: str):
        if not self._token_sah(req):
            return web.Response(status=401, text="token salah")
        ok, alasan = self.anak_diizinkan(req.query.get("anak", ""))
        if not ok:
            return web.Response(status=403, text=alasan)
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(req)
        r = self.ambil_ruang(req.query["anak"])
        (r.guru if peran == "guru" else r.metaverse).add(ws)
        if peran == "guru":
            await ws.send_json({"tipe": "riwayat", "isi": list(r.riwayat)})
        elif r.latar:
            await ws.send_json({"tipe": "latar", "nilai": r.latar})
        await r.ke_guru(r.status(), simpan=False)
        try:
            async for m in ws:
                if m.type != WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(m.data)
                    assert isinstance(data, dict)
                except Exception:
                    await ws.send_json({"tipe": "galat", "pesan": "pesan harus objek JSON"})
                    continue
                if peran == "guru":
                    await self.dari_guru(r, data, ws)
                else:
                    await self.dari_metaverse(r, data, ws, simulasi=False)
        finally:
            r.guru.discard(ws)
            r.metaverse.discard(ws)
            await r.ke_guru(r.status(), simpan=False)
        return ws

    # ---------- pesan masuk ----------
    async def dari_guru(self, r: Ruang, d: dict, ws) -> None:
        tipe = d.get("tipe")
        if tipe == "mulai":
            ta = next((t["id"] for t in self.daftar_ta if norm_id(t["id"]) == norm_id(d.get("ta", ""))), None)
            fase = str(d.get("fase", "")).upper()
            if ta is None or fase not in FASE_SAH:
                await ws.send_json({"tipe": "galat", "pesan": "TA atau fase tidak sah"})
                return
            r.epoch += 1
            r.alasan_epoch = "digantikan MULAI baru"
            r.jeda = False
            r.percakapan = f"{r.id_anak}-{datetime.now(ZONA):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
            r.ta, r.fase = ta, fase
            await self.terapkan_latar(r, f"otomatis dari {ta}" if not r.latar_pilihan else "pilihan guru")
            await self.antre(r, f"[GURU] MULAI {ta} anak {r.id_anak} fase {fase}", "guru")
        elif tipe == "guru" and str(d.get("perintah", "")).upper() in PERINTAH_GURU:
            p = str(d["perintah"]).upper()
            if p == "LANJUT":
                r.jeda = False
            await self.antre(r, f"[GURU] {p}", "guru")
            if p == "SELESAI":
                await r.ke_guru(r.status(), simpan=False)
        elif tipe == "hentikan":
            r.epoch += 1
            r.alasan_epoch = "dihentikan guru"
            r.jeda = True
            await r.ke_metaverse({"tipe": "diam"})
            await r.ke_guru({"tipe": "info", "pesan": "Dihentikan guru. Avatar diam. Tekan LANJUT atau MULAI."})
            await r.ke_guru(r.status(), simpan=False)
            tulis_log({"waktu": sekarang(), "id_anak": r.id_anak, "percakapan": r.percakapan, "acara": "hentikan"})
        elif tipe == "latar":
            nilai = str(d.get("nilai", "")).lower()
            if nilai != "otomatis" and nilai not in self.latar["latar"]:
                await ws.send_json({"tipe": "galat", "pesan": f"latar tidak dikenal: {nilai}"})
                return
            r.latar_pilihan = None if nilai == "otomatis" else nilai
            await self.terapkan_latar(r, "pilihan guru" if r.latar_pilihan else "otomatis")
            await r.ke_guru(r.status(), simpan=False)
        elif tipe == "simulasi" and isinstance(d.get("acara"), dict):
            await self.dari_metaverse(r, d["acara"], ws, simulasi=True)
        else:
            await ws.send_json({"tipe": "galat", "pesan": f"pesan guru tidak dikenal: {d}"})

    async def dari_metaverse(self, r: Ruang, d: dict, ws, simulasi: bool) -> None:
        tipe, nilai = d.get("tipe"), str(d.get("nilai", "")).lower()
        if tipe == "respons" and nilai in RESPONS:
            pesan = f"[SISTEM] respons={nilai}"
        elif tipe == "regulasi" and nilai in REGULASI:
            pesan = f"[SISTEM] regulasi={nilai}"
        elif tipe == "lanjut":
            pesan = "[SISTEM] lanjut"
        elif tipe == "anak" and bersihkan_teks_anak(d.get("teks")):
            pesan = f"[ANAK] {bersihkan_teks_anak(d.get('teks'))}"
        elif tipe == "selesai_diputar":
            return  # tanda dari metaverse bahwa audio selesai; belum dipakai
        else:
            await ws.send_json({"tipe": "galat", "pesan": f"acara tidak dikenal: {d}"})
            return
        if r.percakapan is None:
            await r.ke_guru({"tipe": "info", "pesan": f"Belum ada sesi; diabaikan: {pesan}"})
            return
        if r.jeda and tipe != "regulasi":
            await r.ke_guru({"tipe": "info", "pesan": f"Sesi dijeda; diabaikan: {pesan}"})
            return
        await self.antre(r, pesan, "simulasi" if simulasi else "metaverse")

    # ---------- satu giliran ----------
    async def antre(self, r: Ruang, pesan: str, asal: str) -> None:
        asyncio.create_task(self.giliran(r, pesan, asal, r.epoch, r.percakapan))

    async def giliran(self, r: Ruang, pesan: str, asal: str, epoch: int, percakapan: str) -> None:
        async with r.kunci:
            if epoch != r.epoch and not pesan.startswith("[GURU]"):
                return
            r.giliran += 1
            n = r.giliran
            r.berpikir = True
            await r.ke_guru({"tipe": "masuk", "giliran": n, "asal": asal, "pesan": pesan})
            await r.ke_guru(r.status(), simpan=False)
            galat = None
            try:
                hasil = await asyncio.wait_for(asyncio.to_thread(self.klien.kirim, pesan, percakapan), BATAS_WAKTU)
            except asyncio.TimeoutError:
                hasil, galat = {"teks": "", "tool": [], "durasi": BATAS_WAKTU}, f"tutor tidak menjawab dalam {BATAS_WAKTU:.0f} detik"
            except Exception as e:
                hasil, galat = {"teks": "", "tool": [], "durasi": 0}, f"galat penggerak: {e}"
            r.berpikir = False

            cek = self.penjaga.periksa(hasil["teks"], r.id_anak)
            if galat:
                cek["keluaran"]["catatan_guru"] = f"JEMBATAN: {galat}"
                cek["pelanggaran"] = [galat]
            k = cek["keluaran"]
            tool_asing = [t for t in hasil["tool"] if "asd_rag" not in t and t not in TOOL_META_MCP
                          and t not in {"ambil_task_analysis", "cari_strategi", "profil_anak",
                                        "catat_langkah", "panggil_guru"}]
            dibuang = epoch != r.epoch
            if not dibuang:
                await r.ke_metaverse({"tipe": "tutor", "giliran": n, **{c: k.get(c, "") for c in KOLOM_METAVERSE}})
            await r.ke_guru({"tipe": "tutor", "giliran": n, "pesan": pesan, "keluaran": k,
                             "lolos": cek["lolos"] and not galat, "pelanggaran": cek["pelanggaran"],
                             "peringatan": cek["peringatan"] + ([f"tool di luar asd_rag: {tool_asing}"] if tool_asing else []),
                             "tool": hasil["tool"], "durasi": hasil.get("durasi"), "dibuang": dibuang,
                             "alasan_dibuang": r.alasan_epoch if dibuang else ""})
            baru_dari_tool = time.monotonic() - r.terakhir_tool_panggil < 120
            if k.get("aksi") == "panggil_guru" and not dibuang and not baru_dari_tool:
                await r.ke_guru({"tipe": "panggil_guru", "giliran": n, "sumber": "jawaban",
                                 "tingkat": "tinggi" if not cek["lolos"] or galat else "sedang",
                                 "alasan": k.get("catatan_guru") or "Tutor memanggil guru."})
            await r.ke_guru(r.status(), simpan=False)
            tulis_log({"waktu": sekarang(), "id_anak": r.id_anak, "percakapan": percakapan, "giliran": n,
                       "asal": asal, "pesan": pesan, "jawaban_tutor": hasil["teks"], "tool": hasil["tool"],
                       "durasi": hasil.get("durasi"), "lolos": cek["lolos"] and not galat,
                       "pelanggaran": cek["pelanggaran"], "peringatan": cek["peringatan"],
                       "keluaran": k, "dibuang": dibuang})

    def app(self) -> web.Application:
        a = web.Application()
        async def ke_dasbor(req):
            raise web.HTTPFound("/guru")

        a.add_routes([web.get("/", ke_dasbor), web.get("/guru", self.halaman_guru), web.get("/metaverse", self.halaman_metaverse),
                      web.static("/aset", SINI / "static" / "aset"),
                      web.get("/api/info", self.info),
                      web.post("/internal/panggil_guru", self.internal_panggil_guru), web.get("/ws/guru", self.ws_guru),
                      web.get("/ws/metaverse", self.ws_metaverse)])
        return a


def periksa_awal(j: Jembatan) -> bool:
    """Pastikan Hermes bisa dihubungi dan hanya memberi tool asd_rag kepada tutor."""
    if not hasattr(j.klien, "sehat"):
        return True
    ok, ket = j.klien.sehat()
    if not ok:
        print(f"API server Hermes tidak bisa dihubungi di {j.klien.url}: {ket}\n"
              "Jalankan dulu:  hermes -p tutor-asd gateway   (lihat README, bagian Jembatan)")
        return False
    try:
        tool = j.klien.daftar_tool()
    except Exception as e:
        print(f"PERINGATAN: daftar tool tidak bisa dibaca ({e}). Periksa manual sebelum dipakai.")
        return True
    asing = [t for t in tool if "asd_rag" not in t.lower() and t not in TOOL_META_MCP]
    print("Toolset bawaan yang aktif bagi tutor lewat API server: "
          + (", ".join(tool) if tool else "tidak ada (hanya tool MCP asd_rag)"))
    if asing and os.environ.get("JEMBATAN_IZINKAN_TOOL") != "1":
        print(f"DITOLAK: tutor punya tool di luar asd_rag lewat API server: {asing}\n"
              "Jalankan ulang setup_tutor_profile.py (v6 menambah platform_toolsets.api_server), "
              "lalu restart gateway profil tutor-asd.")
        return False
    return True


def main() -> int:
    j = Jembatan()
    if not periksa_awal(j):
        return 1
    host = os.environ.get("JEMBATAN_HOST", "127.0.0.1")
    port = int(os.environ.get("JEMBATAN_PORT", "8765"))
    print(f"Jembatan aktif: mode {j.mode}, penggerak {j.klien.nama}\n"
          f"Dasbor guru : http://{host}:{port}/guru\n"
          f"Token       : {j.token}   (disimpan di data/.jembatan_token)")
    if j.mode == "dev":
        print("MODE DEV: korpus draft, hanya profil uji. Jangan dipakai dengan anak.")
    web.run_app(j.app(), host=host, port=port, print=None, access_log=None)  # URL WebSocket membawa token
    return 0


if __name__ == "__main__":
    sys.exit(main())
