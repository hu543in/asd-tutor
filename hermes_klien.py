"""Klien Hermes untuk jembatan metaverse dan uji otomatis.

Tiga penggerak dengan antarmuka sama:  kirim(pesan, percakapan) -> dict
  KlienAPI    API server Hermes (`hermes -p tutor-asd gateway`), endpoint /v1/responses.
              Server MCP tetap hangat, jadi jauh lebih cepat daripada CLI. Bawaan.
  KlienCLI    menjalankan `hermes -p tutor-asd chat ...` per pesan (cadangan; lambat).
  KlienPalsu  jawaban berskrip untuk uji tanpa Hermes.

Hasil kirim(): {"teks": str, "tool": [nama tool yang dipanggil], "durasi": detik, "id": str|None}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PROFIL = os.environ.get("HERMES_PROFIL", "tutor-asd")
PEMBUNGKUS = {"tool_call", "mcp__tool_call"}
HANYA_BACA = {"tool_describe", "mcp__tool_describe"}
TOOL_META_MCP = HANYA_BACA | PEMBUNGKUS


def baca_env_profil(profil: str = PROFIL) -> dict:
    """Baca ~/.hermes/profiles/<profil>/.env (KUNCI=nilai)."""
    p = Path.home() / ".hermes" / "profiles" / profil / ".env"
    hasil = {}
    if p.exists():
        for b in p.read_text().splitlines():
            b = b.strip()
            if b and not b.startswith("#") and "=" in b:
                k, v = b.split("=", 1)
                hasil[k.strip()] = v.strip().strip('"').strip("'")
    return hasil


def _nama_dari_argumen(args) -> list[str]:
    """Nama tool di dalam pembungkus tool_call. Hermes 0.21 memakai {"calls": [{"name": ..., "arguments": ...}]}."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return []
    if not isinstance(args, dict):
        return []
    if isinstance(args.get("calls"), list):
        return [n for c in args["calls"] for n in _nama_dari_argumen(c)]
    for k in ("name", "tool", "tool_name"):
        if isinstance(args.get(k), str):
            return [args[k]]
    return []


def tool_aktif(katalog) -> list[str]:
    """Ambil nama tool dari toolset yang enabled. Entri tanpa tanda `enabled` dianggap aktif
    (lebih aman: jembatan menolak berjalan daripada meloloskan tool yang tidak jelas)."""
    data = katalog.get("data") if isinstance(katalog, dict) else katalog
    if not isinstance(data, list):
        return []
    nama = []
    for ts in data:
        if not isinstance(ts, dict) or ts.get("enabled") is False:
            continue
        for t in ts.get("tools") or []:
            n = t if isinstance(t, str) else (t.get("name") if isinstance(t, dict) else None)
            if isinstance(n, str):
                nama.append(n)
    return sorted(set(nama))


class KlienAPI:
    def __init__(self, url: str | None = None, kunci: str | None = None, profil: str = PROFIL,
                 batas_waktu: float = 180):
        env = baca_env_profil(profil)
        port = env.get("API_SERVER_PORT", "8642")
        self.url = (url or os.environ.get("HERMES_API_URL") or f"http://127.0.0.1:{port}").rstrip("/")
        self.kunci = kunci or os.environ.get("HERMES_API_KEY") or env.get("API_SERVER_KEY", "")
        self.profil = profil
        self.batas_waktu = batas_waktu
        self.nama = f"api {self.url}"

    def _minta(self, metode: str, jalur: str, isi: dict | None = None, batas: float | None = None):
        data = json.dumps(isi).encode() if isi is not None else None
        req = urllib.request.Request(self.url + jalur, data=data, method=metode, headers={
            "Authorization": f"Bearer {self.kunci}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=batas or self.batas_waktu) as r:
            return json.loads(r.read().decode() or "{}")

    def sehat(self) -> tuple[bool, str]:
        try:
            self._minta("GET", "/health", batas=5)
            return True, "ok"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code} (periksa API_SERVER_KEY)"
        except Exception as e:
            return False, str(e)

    def daftar_tool(self) -> list[str]:
        """Nama tool dari toolset yang AKTIF bagi agen lewat API server.

        /v1/toolsets (Hermes 0.21) mengembalikan katalog semua toolset bawaan beserta tanda
        `enabled` per toolset; tool MCP (asd_rag) tidak tercantum di katalog ini."""
        return tool_aktif(self._minta("GET", "/v1/toolsets", batas=15))

    def kirim(self, pesan: str, percakapan: str) -> dict:
        t0 = time.monotonic()
        r = self._minta("POST", "/v1/responses", {
            "model": self.profil, "input": pesan, "conversation": percakapan, "store": True})
        teks, alat = urai_respons(r)
        return {"teks": teks, "tool": alat, "durasi": round(time.monotonic() - t0, 1), "id": r.get("id")}


def urai_respons(r: dict) -> tuple[str, list[str]]:
    """Teks jawaban dan nama tool yang benar-benar dipanggil dari satu objek /v1/responses."""
    teks, alat = [], []
    for item in r.get("output") or []:
        jenis = item.get("type")
        if jenis == "message":
            for bag in item.get("content") or []:
                if bag.get("type") in ("output_text", "text") and bag.get("text"):
                    teks.append(bag["text"])
        elif jenis == "function_call":
            n = item.get("name", "")
            if n in HANYA_BACA:
                continue
            if n in PEMBUNGKUS:
                alat.extend(x.lower() for x in (_nama_dari_argumen(item.get("arguments")) or [n]))
            else:
                alat.append(n.lower())
    if not teks and isinstance(r.get("output_text"), str):
        teks = [r["output_text"]]
    return "".join(teks), alat


class KlienCLI:
    """Cadangan bila API server belum bisa dipakai. Satu proses Hermes per pesan."""
    CARA = {
        "resume-sesudah-chat": lambda sid: ["chat", "--resume", sid],
        "resume-sebelum-chat": lambda sid: ["--resume", sid, "chat"],
    }

    def __init__(self, profil: str = PROFIL, cara: str | None = None):
        self.profil = profil
        cache = Path(__file__).resolve().parent / "data" / ".uji_cara_lanjut.json"
        if cara is None and cache.exists():
            cara = json.loads(cache.read_text()).get("cara")
        self.cara = cara if cara in self.CARA else "resume-sesudah-chat"
        self.sesi: dict[str, str] = {}   # percakapan -> ID sesi Hermes
        self.nama = f"cli ({self.cara})"

    def kirim(self, pesan: str, percakapan: str) -> dict:
        t0 = time.monotonic()
        sid = self.sesi.get(percakapan)
        awal = ["chat"] if sid is None else self.CARA[self.cara](sid)
        cmd = [os.environ.get("HERMES_BIN", "hermes"), "-p", self.profil, *awal,
               "-Q", "-q", pesan, "--format", "stream-json"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        teks, alat, sesi_baru = "", [], None
        for baris in p.stdout.splitlines():
            try:
                e = json.loads(baris)
            except json.JSONDecodeError:
                continue
            for k in ("session_id", "sessionId"):
                if isinstance(e.get(k), str):
                    sesi_baru = sesi_baru or e[k]
            if e.get("type") == "tool_use":
                n = str(e.get("name") or e.get("tool") or "")
                if n in PEMBUNGKUS:
                    alat.extend(x.lower() for x in (_nama_dari_argumen(e.get("input") or e.get("arguments")) or [n]))
                elif n and n not in HANYA_BACA:
                    alat.append(n.lower())
            elif e.get("type") == "result" and isinstance(e.get("result"), str):
                teks = e["result"]
            elif e.get("type") == "text" and isinstance(e.get("text"), str) and not teks:
                teks += e["text"]
        if sesi_baru:
            self.sesi[percakapan] = sesi_baru
        if p.returncode != 0 and not teks:
            raise RuntimeError(f"hermes keluar dengan kode {p.returncode}: {p.stderr[-300:]}")
        return {"teks": teks, "tool": alat, "durasi": round(time.monotonic() - t0, 1), "id": sesi_baru}


class KlienPalsu:
    """Jawaban berskrip untuk menguji jembatan tanpa Hermes dan tanpa biaya API."""
    nama = "palsu"

    def __init__(self, jeda: float = 0.0):
        self.jeda = jeda
        self.langkah: dict[str, int] = {}

    def kirim(self, pesan: str, percakapan: str) -> dict:
        time.sleep(self.jeda)
        ujaran = ["Buka keran.", "Basahi tanganmu.", "Ambil sabun.", "Gosok telapak tanganmu."]
        kartu = ["Tangan memutar keran", "Tangan di bawah air", "Tangan menekan sabun", "Telapak bergesekan"]

        def j(**k):
            base = {"pujian": "", "ucap": "", "kartu": "", "aksi": "tunggu", "ta": "TA-02",
                    "langkah": self.langkah.get(percakapan, 1), "catatan_guru": ""}
            base.update(k)
            return json.dumps(base, ensure_ascii=False)

        alat = []
        if pesan.startswith("[GURU] MULAI"):
            self.langkah[percakapan] = 1
            teks, alat = j(ucap=ujaran[0], kartu=kartu[0]), ["ambil_task_analysis"]
        elif "respons=benar" in pesan:
            n = min(self.langkah.get(percakapan, 1) + 1, len(ujaran))
            self.langkah[percakapan] = n
            teks, alat = j(pujian="Hebat!", ucap=ujaran[n - 1], kartu=kartu[n - 1], langkah=n), ["catat_langkah"]
        elif "regulasi=merah" in pesan or "sakit" in pesan:
            teks, alat = j(aksi="panggil_guru", catatan_guru="Eskalasi."), ["panggil_guru"]
        elif "lelucon" in pesan:   # meniru tutor yang melanggar aturan
            teks = j(ucap="Kenapa ayam menyeberang jalan?", aksi="ulang")
        else:
            teks = j(ucap=ujaran[self.langkah.get(percakapan, 1) - 1], aksi="ulang")
        return {"teks": teks, "tool": alat, "durasi": self.jeda, "id": None}


def buat_klien(jenis: str | None = None):
    jenis = (jenis or os.environ.get("JEMBATAN_PENGGERAK", "api")).lower()
    if jenis == "api":
        return KlienAPI()
    if jenis == "cli":
        return KlienCLI()
    if jenis == "palsu":
        return KlienPalsu(float(os.environ.get("JEMBATAN_JEDA_PALSU", "0")))
    raise ValueError(f"penggerak tidak dikenal: {jenis}")
