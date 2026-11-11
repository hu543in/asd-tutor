"""Penjaga keluaran tutor (Langkah 7).

Setiap jawaban JSON dari tutor diperiksa di sini SEBELUM diteruskan ke metaverse (suara avatar).
Kalimat untuk anak (`ucap`, `pujian`) hanya lolos jika persis ada di daftar yang diizinkan:

  - `ujaran` langkah task analysis yang dimuat (mode prod: hanya status valid),
    setelah placeholder diisi dari profil anak;
  - bank ujaran (korpus/bank_ujaran), hanya jika berstatus valid
    (atau ASD_RAG_BANK=draft di mode dev, untuk uji);
  - tiga pujian sementara di SOUL.md.

Jika ada pelanggaran, jawaban tutor diblokir dan diganti keluaran aman
(`ucap: ""`, `aksi: panggil_guru`), dicatat di data/penjaga.jsonl, dan (bila eskalasi aktif)
guru dipanggil lewat data/eskalasi.jsonl dan webhook ASD_RAG_WEBHOOK.

Pemakaian:
  python penjaga.py --anak A01 '{"pujian":"","ucap":"Buka keran.","aksi":"tunggu"}'
  echo '<json per baris>' | python penjaga.py --anak A01           # dari stdin
  python penjaga.py --uji data/uji_tutor_<waktu>.jsonl              # periksa ulang hasil uji
  python penjaga.py --anak A01 --daftar                             # tampilkan kalimat yang diizinkan

Di dalam program lain (jembatan metaverse, Langkah 8):
  from penjaga import Penjaga
  p = Penjaga(eskalasi=True)
  hasil = p.periksa(teks_jawaban_hermes, id_anak="A01")
  kirim_ke_metaverse(hasil["keluaran"])      # selalu kirim 'keluaran', bukan jawaban mentah
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from korpus_lib import DATA, MODE, PLACEHOLDER, isi_placeholder, periksa_entri, semua_entri

AKSI_SAH = {"tunggu", "ulang", "contohkan", "panggil_guru", "tunggu_guru", "selesai", "lapor"}
AKSI_DIAM = {"panggil_guru", "tunggu_guru", "lapor"}          # SOUL.md: ucap wajib kosong
PUJIAN_SEMENTARA = ["Bagus!", "Hebat!", "Kamu berhasil!"]    # sama dengan daftar di SOUL.md
URUTAN_LEVEL = {"dasar": 0, "menengah": 1, "lanjut": 2}
LOG_PENJAGA = DATA / "penjaga.jsonl"
LOG_ESKALASI = DATA / "eskalasi.jsonl"
ZONA = ZoneInfo(os.environ.get("ASD_RAG_TZ", "Asia/Jakarta"))


def norm(s: str) -> str:
    """Bentuk pembanding: huruf kecil, tanpa tanda baca dan kutip, spasi tunggal.
    Hanya perbedaan yang tidak mengubah bunyi kalimat yang diabaikan."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[.,!?;:\"'“”‘’()…]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


def _semua_profil() -> dict:
    path = DATA / "profil.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {norm_id(k): v for k, v in json.load(f).items()}


def _tulis(path, rekaman: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rekaman, ensure_ascii=False) + "\n")


def urai(jawaban) -> tuple[dict | None, list[str]]:
    """Ambil objek JSON dari jawaban tutor. Kembalikan (objek, peringatan)."""
    if isinstance(jawaban, dict):
        return jawaban, []
    teks = (jawaban or "").strip()
    try:
        o = json.loads(teks)
        return (o, []) if isinstance(o, dict) else (None, [])
    except json.JSONDecodeError:
        pass
    obj = None
    for m in re.finditer(r"\{.*\}", teks, flags=re.S):
        try:
            o = json.loads(m.group(0))
            if isinstance(o, dict):
                obj = o
        except json.JSONDecodeError:
            pass
    return obj, (["ada teks di luar objek JSON (tidak diteruskan ke anak)"] if obj else [])


class Penjaga:
    def __init__(self, mode: str | None = None, bank: str | None = None,
                 eskalasi: bool = False, log: bool = True):
        self.mode = (mode or MODE).lower()
        self.bank_mode = (bank or os.environ.get("ASD_RAG_BANK", "valid")).lower()
        self.eskalasi = eskalasi
        self.log = log
        self.webhook = os.environ.get("ASD_RAG_WEBHOOK", "")
        draft = self.mode == "dev"
        # entri yang gagal pemeriksaan aturan tidak pernah dipakai
        self.ta = [d for d in semua_entri("task_analysis", termasuk_draft=draft) if not periksa_entri(d)[0]]
        bank_draft = draft and self.bank_mode == "draft"
        self.bank = [u for b in semua_entri("bank_ujaran", termasuk_draft=bank_draft)
                     if not periksa_entri(b)[0] for u in b.get("ujaran", [])
                     if u.get("status", "valid") != "ditolak"]  # kalimat yang gagal validasi tidak dimuat
        self.profil = _semua_profil()
        self._cache: dict[str, dict] = {}

    # ---------- daftar kalimat yang diizinkan untuk satu anak ----------
    def daftar(self, id_anak: str) -> dict:
        kunci = norm_id(id_anak)
        if kunci in self._cache:
            return self._cache[kunci]
        p = self.profil.get(kunci) or {}
        isian, level = p.get("isian", {}), URUTAN_LEVEL.get(p.get("level", "dasar"), 0)
        ucap, pujian, kartu, ditahan = {}, {}, set(), []

        for d in self.ta:
            for s in d.get("langkah", []):
                teks, kosong = isi_placeholder(s.get("ujaran", ""), isian)
                k, _ = isi_placeholder(s.get("kartu", ""), isian)
                if k:
                    kartu.add(norm(k))
                if kosong:
                    ditahan.append({"sumber": d["id"], "langkah": s.get("nomor"), "ujaran": s["ujaran"],
                                    "placeholder_kosong": kosong})
                    continue
                aktif = level >= URUTAN_LEVEL.get(s.get("level_min", "dasar"), 0)
                ucap.setdefault(norm(teks), []).append(
                    {"teks": teks, "sumber": "TA", "ta": d["id"], "langkah": s.get("nomor"), "aktif": aktif})

        for u in self.bank:
            teks, kosong = isi_placeholder(u["ujaran"], isian)
            if kosong:
                ditahan.append({"sumber": u["id"], "ujaran": u["ujaran"], "placeholder_kosong": kosong})
                continue
            info = {"teks": teks, "sumber": "BANK", "id": u["id"], "kategori": u.get("kategori")}
            ucap.setdefault(norm(teks), []).append(info)
            if u.get("kategori") == "pujian":
                pujian.setdefault(norm(teks), info)

        for t in PUJIAN_SEMENTARA:
            pujian.setdefault(norm(t), {"teks": t, "sumber": "SOUL"})

        hasil = {"ucap": ucap, "pujian": pujian, "kartu": kartu, "ditahan": ditahan}
        self._cache[kunci] = hasil
        return hasil

    # ---------- pemeriksaan satu jawaban ----------
    def periksa(self, jawaban, id_anak: str) -> dict:
        j, peringatan = urai(jawaban)
        pelanggaran: list[str] = []
        if j is None:
            return self._putuskan(None, ["jawaban bukan objek JSON"], peringatan, id_anak, jawaban)

        dft = self.daftar(id_anak)
        bersih = dict(j)
        aksi = j.get("aksi")
        if aksi not in AKSI_SAH:
            pelanggaran.append(f"aksi tidak dikenal: {aksi!r}")

        for kolom in ("pujian", "ucap"):
            if kolom not in j:
                peringatan.append(f"kolom '{kolom}' tidak ada; dianggap kosong")
                bersih[kolom] = ""
            elif not isinstance(j[kolom], str):
                pelanggaran.append(f"kolom '{kolom}' bukan teks")

        pujian = j.get("pujian") if isinstance(j.get("pujian"), str) else ""
        if pujian.strip():
            cocok = dft["pujian"].get(norm(pujian))
            if cocok is None:
                pelanggaran.append(f"pujian di luar daftar: {pujian!r}")
            else:
                bersih["pujian"] = cocok["teks"]

        ucap = j.get("ucap") if isinstance(j.get("ucap"), str) else ""
        if ucap.strip():
            if PLACEHOLDER.search(ucap):
                pelanggaran.append(f"ucap masih berisi placeholder: {ucap!r}")
            elif norm(ucap) not in dft["ucap"]:
                pelanggaran.append(f"ucap di luar korpus: {ucap!r}")
            else:
                cocok = dft["ucap"][norm(ucap)]
                bersih["ucap"] = cocok[0]["teks"]
                peringatan += self._cek_posisi(cocok, j)
            if aksi in AKSI_DIAM:
                pelanggaran.append(f"ucap harus kosong saat aksi {aksi}")
            elif aksi == "selesai":
                peringatan.append("ucap terisi saat aksi selesai (SOUL.md: kosong)")

        kartu = j.get("kartu")
        if isinstance(kartu, str) and kartu.strip() and norm(kartu) not in dft["kartu"]:
            peringatan.append(f"kartu tidak dikenal di korpus: {kartu!r}")

        return self._putuskan(bersih, pelanggaran, peringatan, id_anak, jawaban)

    @staticmethod
    def _cek_posisi(cocok: list[dict], j: dict) -> list[str]:
        """Peringatan konteks (tidak memblokir): ucap dari TA atau langkah lain, atau langkah nonaktif."""
        dari_ta = [c for c in cocok if c["sumber"] == "TA"]
        if not dari_ta or any(c["sumber"] == "BANK" for c in cocok):
            return []
        hasil = []
        ta = j.get("ta")
        if ta:
            sama_ta = [c for c in dari_ta if norm_id(c["ta"]) == norm_id(str(ta))]
            if not sama_ta:
                hasil.append(f"ucap berasal dari {dari_ta[0]['ta']}, bukan {ta}")
            elif j.get("langkah") not in (None, "") and not any(
                    str(c["langkah"]) == str(j.get("langkah")) for c in sama_ta):
                hasil.append(f"ucap milik langkah {sama_ta[0]['langkah']}, jawaban menyebut langkah {j.get('langkah')}")
        if not any(c["aktif"] for c in dari_ta):
            hasil.append("ucap berasal dari langkah di atas level anak (nonaktif)")
        return hasil

    def _putuskan(self, bersih, pelanggaran, peringatan, id_anak, mentah) -> dict:
        lolos = not pelanggaran
        if lolos:
            keluaran = bersih
        else:
            asli = (bersih or {}).get("catatan_guru", "")
            keluaran = {"pujian": "", "ucap": "", "kartu": "", "aksi": "panggil_guru",
                        "ta": (bersih or {}).get("ta", ""), "langkah": (bersih or {}).get("langkah", ""),
                        "catatan_guru": "PENJAGA memblokir jawaban tutor: " + "; ".join(pelanggaran)
                                        + (f" | catatan tutor: {asli}" if asli else "")}
        hasil = {"lolos": lolos, "pelanggaran": pelanggaran, "peringatan": peringatan, "keluaran": keluaran}

        if self.log and (pelanggaran or peringatan):
            _tulis(LOG_PENJAGA, {"waktu": datetime.now(ZONA).isoformat(timespec="seconds"),
                                 "id_anak": norm_id(id_anak), "mode": self.mode, "lolos": lolos,
                                 "pelanggaran": pelanggaran, "peringatan": peringatan,
                                 "jawaban_tutor": mentah if isinstance(mentah, (dict, str)) else str(mentah)})
        if self.eskalasi and not lolos:
            self._panggil_guru(id_anak, "; ".join(pelanggaran))
        return hasil

    def _panggil_guru(self, id_anak: str, alasan: str) -> None:
        rekaman = {"waktu": datetime.now(ZONA).isoformat(timespec="seconds"), "id_anak": norm_id(id_anak),
                   "alasan": f"Penjaga keluaran: {alasan}", "tingkat": "sedang", "sumber": "penjaga"}
        _tulis(LOG_ESKALASI, rekaman)
        if self.webhook:
            try:
                req = urllib.request.Request(self.webhook, data=json.dumps(rekaman).encode(),
                                             headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass  # kegagalan webhook tidak boleh menghentikan pemblokiran


# ---------- baris perintah ----------
def _cetak_daftar(p: Penjaga, id_anak: str) -> None:
    d = p.daftar(id_anak)
    print(f"Anak {norm_id(id_anak)} | mode {p.mode} | bank {p.bank_mode} | "
          f"{len(p.ta)} TA, {len(p.bank)} kalimat bank dimuat\n")
    print("Pujian:")
    for v in d["pujian"].values():
        print(f"  {v['teks']}  ({v['sumber']})")
    print("\nUcap:")
    for v in d["ucap"].values():
        c = v[0]
        asal = f"{c['ta']} langkah {c['langkah']}" if c["sumber"] == "TA" else c["id"]
        print(f"  {c['teks']}  ({asal}{'' if c.get('aktif', True) else ', nonaktif'})")
    if d["ditahan"]:
        print("\nDitahan karena placeholder kosong di profil:")
        for x in d["ditahan"]:
            print(f"  {x['ujaran']}  ({x['sumber']}: {', '.join(x['placeholder_kosong'])})")


def _uji_ulang(p: Penjaga, path: str, id_anak: str) -> int:
    n = blok = 0
    print(f"Periksa ulang {path} (mode {p.mode}, anak {id_anak})\n")
    with open(path, encoding="utf-8") as f:
        for baris in f:
            r = json.loads(baris)
            jawaban = r.get("teks") or r.get("json")
            if not jawaban:
                continue
            h = p.periksa(jawaban, id_anak)
            n += 1
            blok += not h["lolos"]
            if not h["lolos"] or h["peringatan"]:
                tanda = "BLOKIR" if not h["lolos"] else "CEK"
                print(f"[{tanda:6}] skenario {r.get('skenario')} langkah {r.get('langkah')}: {r.get('pesan')}")
                for x in h["pelanggaran"]:
                    print(f"          pelanggaran: {x}")
                for x in h["peringatan"]:
                    print(f"          peringatan : {x}")
    print(f"\n{n} jawaban diperiksa, {blok} diblokir.")
    return 0 if blok == 0 else 3


def main() -> int:
    ap = argparse.ArgumentParser(description="Penjaga keluaran tutor ASD")
    ap.add_argument("jawaban", nargs="*", help="jawaban JSON tutor; kosong = baca stdin per baris")
    ap.add_argument("--anak", default="A01")
    ap.add_argument("--mode", choices=["prod", "dev"], default=None, help="bawaan: ASD_RAG_MODE")
    ap.add_argument("--bank", choices=["valid", "draft"], default=None, help="bawaan: ASD_RAG_BANK atau valid")
    ap.add_argument("--uji", metavar="JSONL", help="periksa ulang file hasil uji_tutor.py")
    ap.add_argument("--daftar", action="store_true", help="tampilkan kalimat yang diizinkan")
    ap.add_argument("--tanpa-log", action="store_true")
    a = ap.parse_args()

    p = Penjaga(mode=a.mode, bank=a.bank, log=not a.tanpa_log)
    if a.daftar:
        _cetak_daftar(p, a.anak)
        return 0
    if a.uji:
        return _uji_ulang(p, a.uji, a.anak)
    sumber = a.jawaban or [b for b in sys.stdin if b.strip()]
    semua_lolos = True
    for jw in sumber:
        h = p.periksa(jw, a.anak)
        semua_lolos &= h["lolos"]
        print(json.dumps(h, ensure_ascii=False))
    return 0 if semua_lolos else 3


if __name__ == "__main__":
    sys.exit(main())
