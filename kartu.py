"""Kelola gambar kartu untuk klien metaverse.

Setiap nama kartu di korpus (kolom `kartu` pada langkah task analysis) dapat diberi gambar.
Gambar hanya ditampilkan ke anak bila sudah disetujui guru (`disetujui: true` di kartu.json);
selain itu kartu tetap tampil sebagai teks.

Sumber gambar bisa dua macam:
  - piktogram ARASAAC (penulis Sergio Palao, milik Pemerintah Aragon; lisensi CC BY-NC-SA 4.0),
    dicari dengan kata kunci bahasa Inggris;
  - foto atau gambar sendiri (mis. foto wastafel sekolah), cukup disimpan sebagai
    static/aset/kartu/<berkas> lalu disetujui.

Perintah:
  python kartu.py daftar                         # buat/perbarui kartu.json dari korpus, tampilkan status
  python kartu.py kandidat [--kartu TEKS] [-n 6] # cari piktogram ARASAAC, buat galeri _kandidat/index.html
  python kartu.py pasang --kartu TEKS --id 1234  # unduh piktogram terpilih menjadi gambar kartu
  python kartu.py sendiri --kartu TEKS --berkas foto.jpg   # pakai gambar sendiri (sudah ada di folder kartu)
  python kartu.py setujui --kartu TEKS [--kartu TEKS2 ...] [--batal]   # guru menyetujui (atau membatalkan)
  python kartu.py buatan                         # pasang piktogram buatan proyek, buat halaman tinjauan
  python kartu.py periksa [--anak A01]           # cek tiap langkah: gambar apa yang tampil di papan, dan
                                                 # kartu yang dikirim tutor di log jembatan
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from korpus_lib import semua_entri

SINI = Path(__file__).resolve().parent
FOLDER = SINI / "static" / "aset" / "kartu"
BERKAS_JSON = FOLDER / "kartu.json"
KANDIDAT = FOLDER / "_kandidat"
CARI = "https://api.arasaac.org/v1/pictograms/en/search/{q}"
GAMBAR = "https://static.arasaac.org/pictograms/{id}/{id}_500.png"
ATRIBUSI_ARASAAC = ("Piktogram: Sergio Palao. Asal: ARASAAC (https://arasaac.org). "
                    "Milik Pemerintah Aragon (Spanyol). Lisensi CC BY-NC-SA 4.0.")

# Kata kunci awal (bahasa Inggris) untuk pencarian ARASAAC. Guru boleh mengubahnya di kartu.json.
# Beberapa kata kunci dipisah ";" dicari semuanya. Diperbarui 30 Okt 2026 untuk kartu yang kandidat awalnya kurang sesuai.
KATA_KUNCI_BARU = {
    "Dua anak duduk": "children sitting; sit together; classmates; friends",
    "Guru melambai": "teacher greeting; wave hello; hello; teacher",
    "Jari saling menyilang": "wash between fingers; interlace fingers; wash hands",
    "Kartu angka dengan kotak kosong sebanyak angka": "number card; numbers; count",
    "Kartu istirahat": "take a break; break; rest; relax",
    "Kartu menunjuk teman": "your turn; turn; point at",
    "Kotak bekal di tas": "lunchbox; backpack; take out",
    "Kotak masuk tas": "put in backpack; put away; backpack",
    "Kursi dengan foto anak": "my chair; chair; seat",
    "Loker dengan foto anak": "locker; cupboard; cubby",
    "Papan jadwal": "visual schedule; daily routine; timetable; agenda",
    "Pensil masuk kotak": "put pencil away; pencil case; put in",
    "Satu benda di satu kotak": "one to one; put in; count",
    "Tangan di [pengering kelas]": "dry hands; towel; dry",
    "Tangan di bawah air": "wet hands; water; tap water",
    "Tangan melambai": "wave; hello; goodbye",
    "Tangan menaruh balok": "stack blocks; build blocks; blocks; place",
    "Tas di dalam loker": "hang up bag; put bag in locker; locker",
    "Telapak bergesekan": "rub hands; lather; soap hands",
    "Telapak menggosok punggung tangan": "wash back of hands; scrub hands; wash hands",
}
KATA_KUNCI = {
    "Pintu kelas": "door", "Guru melambai": "teacher wave", "Anak masuk kelas": "enter classroom",
    "Loker dengan foto anak": "locker", "Tas dilepas": "take off backpack", "Tas di dalam loker": "backpack locker",
    "Kursi dengan foto anak": "chair", "Anak duduk": "sit down",
    "Tangan memutar keran": "turn on the tap", "Tangan di bawah air": "wet hands", "Tangan menekan sabun": "soap",
    "Telapak bergesekan": "rub hands", "Telapak menggosok punggung tangan": "wash hands",
    "Jari saling menyilang": "wash hands", "Busa dibilas air": "rinse hands", "Tangan menutup keran": "turn off the tap",
    "Tangan di [pengering kelas]": "dry hands",
    "Kotak bekal di tas": "lunch box", "Kotak bekal di meja": "lunch box", "Tutup terbuka": "open",
    "Sendok": "spoon", "Anak makan": "eat", "Tutup tertutup": "close", "Kotak masuk tas": "put away",
    "Pensil di meja": "pencil", "Kotak pensil": "pencil case", "Pensil masuk kotak": "put away",
    "Kotak tertutup": "close", "Kotak di rak bergambar": "shelf",
    "Anak menghadap guru": "look at the teacher", "Tangan melambai": "wave", "Balon kata 'Selamat pagi'": "good morning",
    "Guru tersenyum": "teacher", "Benda di meja": "table", "Kartu 'Tolong'": "help", "Jari menunjuk": "point",
    "Guru membantu": "help", "Kartu 'Terima kasih'": "thank you",
    "Dua anak duduk": "friends", "Kartu bergambar wajah": "face", "Kartu menunjuk teman": "my turn",
    "Tangan menaruh balok": "blocks",
    "Jam pasir": "hourglass", "Papan jadwal": "schedule", "Gambar aktivitas sekarang": "now",
    "Kotak 'selesai'": "finished", "Gambar aktivitas berikutnya": "next", "Tempat aktivitas berikutnya": "go",
    "Kartu istirahat": "break", "Sudut tenang": "calm corner", "Bantal duduk": "cushion",
    "Benda pilihan anak": "toy", "Anak beristirahat": "rest", "Kartu siap": "ready", "Meja anak": "desk",
    "Kartu angka dengan kotak kosong sebanyak angka": "numbers", "Mulut berbicara": "speak",
    "Satu benda di satu kotak": "count", "Jari menunjuk benda": "point", "Tombol selesai": "finished",
}


# Piktogram buatan proyek (CC0, digambar dengan alat/piktogram/gambar.js) untuk kartu yang tidak
# punya padanan yang cocok di ARASAAC. Tetap harus disetujui guru sebelum tampil ke anak.
PETA_BUATAN = {
    "Guru melambai": "guru-melambai.png", "Jari saling menyilang": "jari-saling-menyilang.png",
    "Kartu angka dengan kotak kosong sebanyak angka": "kartu-angka-3.png", "Kartu istirahat": "kartu-istirahat.png",
    "Kartu menunjuk teman": "kartu-menunjuk-teman.png", "Kotak bekal di tas": "kotak-bekal-di-tas.png",
    "Kotak masuk tas": "kotak-masuk-tas.png", "Kursi dengan foto anak": "kursi-dengan-foto-anak.png",
    "Loker dengan foto anak": "loker-dengan-foto-anak.png", "Papan jadwal": "papan-jadwal.png",
    "Pensil masuk kotak": "pensil-masuk-kotak.png", "Satu benda di satu kotak": "satu-benda-satu-kotak.png",
    "Tangan di [pengering kelas]": "tangan-di-pengering.png", "Tangan di bawah air": "tangan-di-bawah-air.png",
    "Tangan melambai": "tangan-melambai.png", "Tangan menaruh balok": "tangan-menaruh-balok.png",
    "Tas di dalam loker": "tas-di-dalam-loker.png", "Telapak bergesekan": "telapak-bergesekan.png",
    "Telapak menggosok punggung tangan": "telapak-menggosok-punggung-tangan.png",
}


def slug(teks: str) -> str:
    t = unicodedata.normalize("NFKD", teks).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\[([^\]]+)\]", r"\1", t)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60] or "kartu"


def muat() -> dict:
    if BERKAS_JSON.exists():
        return json.loads(BERKAS_JSON.read_text(encoding="utf-8"))
    return {"atribusi": {}, "kartu": []}


def simpan(d: dict) -> None:
    FOLDER.mkdir(parents=True, exist_ok=True)
    d["kartu"].sort(key=lambda k: k["kartu"].lower())
    BERKAS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def cari_entri(d: dict, teks: str) -> dict:
    for k in d["kartu"]:
        if k["kartu"].lower() == teks.strip().lower():
            return k
    raise SystemExit(f"Kartu '{teks}' tidak ada di kartu.json. Jalankan dulu: python kartu.py daftar")


def ambil(url: str, batas: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "asd-rag-kartu/1.0"})
    with urllib.request.urlopen(req, timeout=batas) as r:
        return r.read()


def perintah_daftar(a) -> int:
    d = muat()
    ada = {k["kartu"]: k for k in d["kartu"]}
    pemakai: dict[str, list[str]] = {}
    for e in semua_entri("task_analysis", termasuk_draft=True):
        for s in e.get("langkah", []):
            if s.get("kartu"):
                pemakai.setdefault(s["kartu"], []).append(f"{e['id']}/{s['nomor']}")
    for teks, dipakai in pemakai.items():
        k = ada.get(teks) or {"kartu": teks, "berkas": "", "sumber": "", "arasaac_id": None,
                              "kata_kunci": KATA_KUNCI.get(teks, ""), "disetujui": False}
        k["dipakai_di"] = dipakai
        if getattr(a, "kata_baru", False) and teks in KATA_KUNCI_BARU and not k.get("disetujui"):
            k["kata_kunci"] = KATA_KUNCI_BARU[teks]
        ada[teks] = k
    for teks, k in ada.items():
        if teks not in pemakai:
            k["dipakai_di"] = []
    d["kartu"] = list(ada.values())
    simpan(d)
    total = len(pemakai)
    bergambar = sum(1 for k in d["kartu"] if k["berkas"] and (FOLDER / k["berkas"]).exists())
    setuju = sum(1 for k in d["kartu"] if k["disetujui"] and k["berkas"] and (FOLDER / k["berkas"]).exists())
    print(f"{total} kartu di korpus · {bergambar} punya gambar · {setuju} disetujui guru")
    for k in d["kartu"]:
        tanda = "SETUJU" if k["disetujui"] else ("gambar" if k["berkas"] else "teks  ")
        print(f"  [{tanda}] {k['kartu']}  ({', '.join(k['dipakai_di']) or 'tidak dipakai lagi'})")
    print(f"\nTersimpan: {BERKAS_JSON}")
    return 0


def perintah_kandidat(a) -> int:
    d = muat()
    daftar = [cari_entri(d, t) for t in a.kartu] if a.kartu else [k for k in d["kartu"] if not k["berkas"] and k["dipakai_di"]]
    KANDIDAT.mkdir(parents=True, exist_ok=True)
    bagian = []
    for k in daftar:
        q = a.kata or k.get("kata_kunci") or ""
        if not q:
            print(f"  lewati '{k['kartu']}': kata_kunci kosong di kartu.json")
            continue
        ids = []
        for kata in [x.strip() for x in q.split(";") if x.strip()]:
            try:
                hasil = json.loads(ambil(CARI.format(q=urllib.parse.quote(kata))))
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    print(f"  galat ARASAAC untuk '{kata}': HTTP {e.code}")
                continue
            except Exception as e:
                print(f"  ARASAAC tidak bisa dihubungi ({e}). Periksa koneksi internet server.")
                return 1
            ids += [h["_id"] for h in hasil[: a.n] if "_id" in h and h["_id"] not in ids]
        folder = KANDIDAT / slug(k["kartu"])
        folder.mkdir(parents=True, exist_ok=True)
        gambar = []
        for i in ids:
            f = folder / f"{i}.png"
            if not f.exists():
                try:
                    f.write_bytes(ambil(GAMBAR.format(id=i)))
                except Exception as e:
                    print(f"  gagal mengunduh piktogram {i}: {e}")
                    continue
            gambar.append(i)
        print(f"  {k['kartu']}: kata kunci '{q}' → {len(gambar)} kandidat")
        sel = "".join(f'<figure><img src="{slug(k["kartu"])}/{i}.png" alt="piktogram {i}" loading="lazy">'
                      f'<figcaption>{i}</figcaption></figure>' for i in gambar) or "<p>Tidak ada hasil. Ubah kata_kunci.</p>"
        perintah = html.escape(f'python kartu.py pasang --kartu "{k["kartu"]}" --id <ID>')
        bagian.append(f'<section><h2>{html.escape(k["kartu"])}</h2><p>Kata kunci: <b>{html.escape(q)}</b> · '
                      f'dipakai di {html.escape(", ".join(k["dipakai_di"]))}</p><div class="kisi">{sel}</div>'
                      f'<p class="cmd">{perintah}</p></section>')
    halaman = ("<!doctype html><html lang='id'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
               "<title>Kandidat Kartu</title><style>body{font:15px system-ui,sans-serif;margin:0 auto;max-width:1100px;"
               "padding:16px;background:#f6f6f2;color:#2f3a37}section{background:#fff;border:1px solid #d5ddd9;border-radius:10px;"
               "padding:12px 16px;margin:12px 0}.kisi{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0;text-align:center}"
               "img{width:140px;height:140px;object-fit:contain;border:1px solid #e1e6e3;border-radius:8px;background:#fff}"
               "figcaption{font-size:13px;color:#5d6b67}.cmd{font-family:monospace;font-size:12.5px;color:#5d6b67}"
               "footer{font-size:12.5px;color:#5d6b67}</style>"
               "<h1>Kandidat gambar kartu</h1><p>Pilih piktogram yang paling jelas untuk setiap kartu, lalu jalankan perintah "
               "di bawahnya dengan ID pilihan. Gambar baru tampil ke anak setelah disetujui guru.</p>"
               + "".join(bagian) + f"<footer>{html.escape(ATRIBUSI_ARASAAC)}</footer></html>")
    (KANDIDAT / "index.html").write_text(halaman, encoding="utf-8")
    print(f"\nGaleri: /aset/kartu/_kandidat/index.html (buka lewat https://<domain>/aset/kartu/_kandidat/index.html)")
    return 0


def perintah_pasang(a) -> int:
    d = muat()
    k = cari_entri(d, a.kartu)
    nama = f"{slug(k['kartu'])}.png"
    calon = KANDIDAT / slug(k["kartu"]) / f"{a.id}.png"
    data = calon.read_bytes() if calon.exists() else ambil(GAMBAR.format(id=a.id))
    (FOLDER / nama).write_bytes(data)
    k.update(berkas=nama, arasaac_id=a.id, sumber="arasaac", disetujui=False)
    d.setdefault("atribusi", {})["arasaac"] = ATRIBUSI_ARASAAC
    simpan(d)
    print(f"Terpasang: {nama} (ARASAAC {a.id}). Belum tampil ke anak sampai disetujui:\n"
          f'  python kartu.py setujui --kartu "{k["kartu"]}"')
    return 0


def perintah_sendiri(a) -> int:
    d = muat()
    k = cari_entri(d, a.kartu)
    if not (FOLDER / a.berkas).exists():
        raise SystemExit(f"Berkas {FOLDER / a.berkas} belum ada. Salin gambarnya ke folder itu dulu.")
    k.update(berkas=a.berkas, arasaac_id=None, sumber="sendiri", disetujui=False)
    simpan(d)
    print(f'Dipakai: {a.berkas}. Setujui dengan: python kartu.py setujui --kartu "{k["kartu"]}"')
    return 0


def perintah_buatan(_a) -> int:
    """Pasang piktogram buatan proyek ke kartunya (belum disetujui) dan buat halaman tinjauan."""
    d = muat()
    sel = []
    for teks, berkas in PETA_BUATAN.items():
        try:
            k = cari_entri(d, teks)
        except SystemExit:
            print(f"  lewati '{teks}': tidak ada di kartu.json")
            continue
        if k.get("disetujui") and k.get("sumber") != "buatan":
            print(f"  lewati '{teks}': sudah memakai gambar lain yang disetujui")
            continue
        k.update(berkas=f"buatan/{berkas}", arasaac_id=None, sumber="buatan", disetujui=False)
        sel.append(f'<figure><img src="../buatan/{berkas}" alt="{html.escape(teks)}"><figcaption>{html.escape(teks)}</figcaption>'
                   f'<code>python kartu.py setujui --kartu "{html.escape(teks)}"</code></figure>')
    simpan(d)
    KANDIDAT.mkdir(parents=True, exist_ok=True)
    (KANDIDAT / "buatan.html").write_text(
        "<!doctype html><html lang='id'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Piktogram Buatan</title><style>body{font:15px system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px;"
        "background:#f6f6f2;color:#2f3a37}.kisi{display:flex;flex-wrap:wrap;gap:12px}figure{margin:0;background:#fff;border:1px solid #d5ddd9;"
        "border-radius:10px;padding:10px;width:230px}img{width:210px;height:210px}figcaption{font-weight:600;margin:6px 0}"
        "code{font-size:11px;color:#5d6b67;word-break:break-word}</style><h1>Piktogram buatan proyek</h1>"
        "<p>Periksa setiap gambar bersama guru. Setujui yang sesuai dengan perintah di bawahnya.</p>"
        f"<div class='kisi'>{''.join(sel)}</div></html>", encoding="utf-8")
    print(f"{len(sel)} piktogram buatan dipasang (belum disetujui).")
    print("Tinjau di: https://<domain>/aset/kartu/_kandidat/buatan.html")
    return 0


def perintah_setujui(a) -> int:
    d = muat()
    for teks in a.kartu:
        k = cari_entri(d, teks)
        if not a.batal and not (k["berkas"] and (FOLDER / k["berkas"]).exists()):
            print(f"Lewati (belum punya gambar): {k['kartu']}")
            continue
        k["disetujui"] = not a.batal
        print(f"{'Dibatalkan' if a.batal else 'Disetujui'}: {k['kartu']}")
    simpan(d)
    return 0


def _cocok_klien(d: dict, teks: str):
    """Sama dengan klien metaverse: nama persis didahulukan, lalu pola [placeholder]."""
    t = teks.lower()
    for k in d["kartu"]:
        if k["kartu"].lower() == t:
            return k
    for k in d["kartu"]:
        if "[" in k["kartu"]:
            pola = "^" + ".+".join(re.escape(x) for x in re.split(r"\[[^\]]+\]", k["kartu"])) + "$"
            if re.match(pola, teks, re.I):
                return k
    return None


def perintah_periksa(a) -> int:
    from korpus_lib import DATA, isi_placeholder
    from penjaga import norm, norm_id
    d = muat()
    profil = {}
    p = DATA / "profil.json"
    if p.exists():
        profil = {norm_id(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    isian = (profil.get(norm_id(a.anak)) or {}).get("isian", {})
    print(f"Anak {a.anak}: isian placeholder {isian or '(kosong)'}\n")
    masalah, harapan = 0, {}
    for e in semua_entri("task_analysis", termasuk_draft=True):
        for s in e.get("langkah", []):
            asli = s.get("kartu", "")
            kartu, kosong = isi_placeholder(asli, isian)
            kartu = kartu or asli
            ujaran, _ = isi_placeholder(s.get("ujaran", ""), isian)
            harapan[(norm_id(e["id"]), norm(ujaran))] = kartu
            k = _cocok_klien(d, kartu)
            if not asli:
                status = "TANPA KARTU di YAML"
            elif k is None:
                status = "tidak ada di kartu.json -> teks"
            elif not k.get("berkas"):
                status = "belum punya gambar -> teks"
            elif not (FOLDER / k["berkas"]).exists():
                status = f"BERKAS HILANG ({k['berkas']}) -> teks"
            elif not k.get("disetujui"):
                status = "gambar belum disetujui -> teks"
            else:
                status = f"gambar {k['berkas']}"
            if not status.startswith("gambar "):
                masalah += 1
            print(f"  {e['id']}/{s['nomor']:<2} {kartu:<40} {status}" + (f"  [placeholder kosong: {kosong}]" if kosong else ""))
    print(f"\n{masalah} langkah tampil sebagai teks (bukan gambar).")

    log = DATA / "jembatan.jsonl"
    if not log.exists():
        return 0
    kosong_k, beda = [], []
    for baris in log.read_text(encoding="utf-8").splitlines()[-2000:]:
        try:
            r = json.loads(baris)
        except json.JSONDecodeError:
            continue
        k = r.get("keluaran") or {}
        if not r.get("lolos") or r.get("dibuang") or not k.get("ucap"):
            continue
        h = harapan.get((norm_id(str(k.get("ta", ""))), norm(k["ucap"])))
        if h is None:
            continue
        if not k.get("kartu"):
            kosong_k.append((r.get("waktu"), k.get("ta"), k["ucap"], h))
        elif norm(k["kartu"]) != norm(h):
            beda.append((r.get("waktu"), k.get("ta"), k["ucap"], k["kartu"], h))
    print(f"\nLog jembatan: {len(kosong_k)} jawaban tanpa kartu, {len(beda)} jawaban dengan kartu lain dari langkahnya.")
    for w, ta, u, h in kosong_k[-8:]:
        print(f"  {w} {ta} '{u}': kartu KOSONG (seharusnya '{h}')")
    for w, ta, u, kk, h in beda[-8:]:
        print(f"  {w} {ta} '{u}': kartu '{kk}' (seharusnya '{h}')")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Kelola gambar kartu")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("daftar")
    p.add_argument("--kata-baru", action="store_true", help="pakai kata kunci baru untuk kartu yang belum disetujui")
    p = sub.add_parser("kandidat"); p.add_argument("--kartu", action="append")
    p.add_argument("--kata", help="kata kunci pengganti, beberapa dipisah ;"); p.add_argument("-n", type=int, default=6)
    p = sub.add_parser("pasang"); p.add_argument("--kartu", required=True); p.add_argument("--id", type=int, required=True)
    p = sub.add_parser("sendiri"); p.add_argument("--kartu", required=True); p.add_argument("--berkas", required=True)
    p = sub.add_parser("setujui"); p.add_argument("--kartu", required=True, action="append"); p.add_argument("--batal", action="store_true")
    sub.add_parser("buatan")
    p = sub.add_parser("periksa"); p.add_argument("--anak", default="A01")
    a = ap.parse_args()
    return {"daftar": perintah_daftar, "kandidat": perintah_kandidat, "pasang": perintah_pasang,
            "sendiri": perintah_sendiri, "setujui": perintah_setujui, "buatan": perintah_buatan,
            "periksa": perintah_periksa}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
