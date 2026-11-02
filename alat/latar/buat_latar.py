"""Membuat static/aset/latar/latar.json: beberapa latar ruangan untuk klien metaverse.

Setiap latar = cangkang ruangan bersama (lantai, tiga dinding, plafon) dengan warnanya sendiri,
ditambah benda-benda sederhana A-Frame. Posisi avatar (-1,25; 0; -2,6) dan papan kartu
(1,0; 1,65; -3,1) sama di semua latar agar anak selalu tahu di mana melihat.

Prinsip tampilan: warna lembut, sedikit benda, tidak ada yang berkedip atau bergerak di latar.

Jalankan ulang setelah mengubah berkas ini:
    python alat/latar/buat_latar.py
Berkas JSON hasilnya juga boleh diedit langsung (mis. mengganti warna).
"""
import json
from pathlib import Path

KELUAR = Path(__file__).resolve().parents[2] / "static" / "aset" / "latar" / "latar.json"


def b(el, **atr):
    """Satu benda A-Frame. el: plane, box, cylinder, sphere, circle, cone, ring, torus, entity."""
    anak = atr.pop("anak", None)
    d = {"el": el, **{k.replace("_", "-"): v for k, v in atr.items()}}
    if anak:
        d["anak"] = anak
    return d


# ---------- cangkang ruangan (warna diisi dari tiap latar) ----------
DASAR = [
    b("plane", rotation="-90 0 0", width=9, height=9, position="0 0 -1.5", color="{lantai}"),
    b("plane", position="0 1.6 -4", width=9, height=3.2, color="{dinding}"),
    b("plane", position="-4.5 1.6 -1.5", rotation="0 90 0", width=5, height=3.2, color="{samping}"),
    b("plane", position="4.5 1.6 -1.5", rotation="0 -90 0", width=5, height=3.2, color="{samping}"),
    b("plane", position="0 3.2 -1.5", rotation="90 0 0", width=9, height=5, color="{plafon}"),
    b("plane", position="0 0.06 -3.99", width=9, height=0.12, color="{list}"),
    b("plane", position="-4.49 0.06 -1.5", rotation="0 90 0", width=5, height=0.12, color="{list}"),
    b("plane", position="4.49 0.06 -1.5", rotation="0 -90 0", width=5, height=0.12, color="{list}"),
]


def karpet(warna, radius=0.95):
    return b("circle", rotation="-90 0 0", radius=radius, position="-1.25 0.005 -2.6", color=warna)


def jendela_kiri():
    return b("entity", position="-4.48 1.75 -2.2", rotation="0 90 0", anak=[
        b("plane", width=1.9, height=1.25, color="#bfd3cc"),
        b("plane", width=1.76, height=1.11, position="0 0 0.005", color="#d4e8f0"),
        b("plane", width=0.04, height=1.11, position="0 0 0.01", color="#bfd3cc"),
        b("plane", width=1.76, height=0.04, position="0 0 0.01", color="#bfd3cc"),
    ])


def tanaman(pos):
    return b("entity", position=pos, anak=[
        b("cylinder", radius=0.2, height=0.42, position="0 0.21 0", color="#c9a98a"),
        b("sphere", radius=0.38, position="0 0.75 0", color="#9cbfa4"),
        b("sphere", radius=0.26, position="0.2 1.0 0.05", color="#8fb59a"),
    ])


def rak_rendah(pos, isi):
    return b("entity", position=pos, anak=[
        b("box", width=1.5, height=0.9, depth=0.35, position="0 0.45 0", color="#c8b394"),
        b("box", width=1.4, height=0.03, depth=0.33, position="0 0.45 0.01", color="#b19c7c"),
        *isi,
    ])


BUKU = [
    b("box", width=0.1, height=0.32, depth=0.25, position="-0.55 1.06 0", color="#9fb7c9"),
    b("box", width=0.1, height=0.28, depth=0.25, position="-0.43 1.04 0", color="#c9b38a"),
    b("box", width=0.1, height=0.3, depth=0.25, position="-0.31 1.05 0", color="#a9c4ad"),
    b("box", width=0.34, height=0.2, depth=0.25, position="0.4 1.0 0", color="#d7c7a7"),
]


def meja_anak(pos="1.0 0 -2.15"):
    kaki = [b("cylinder", radius=0.025, height=0.5, position=f"{x} 0.25 {z}", color="#b8a283")
            for x in (-0.48, 0.48) for z in (-0.22, 0.22)]
    return b("entity", position=pos, anak=[
        b("box", width=1.1, height=0.05, depth=0.55, position="0 0.52 0", color="#d9c2a0"), *kaki])


# ---------- 1. ruang kelas ----------
jadwal = b("entity", position="-4.47 1.55 -0.9", rotation="0 90 0", anak=[
    b("plane", width=0.5, height=1.5, color="#d8d2c2"),
    *[b("plane", width=0.36, height=0.26, position=f"0 {0.5 - i * 0.33:.2f} 0.005", color=c)
      for i, c in enumerate(["#cfe0d6", "#e6d7b8", "#cdd9e6", "#e3cfcf"])],
])
KELAS = {
    "nama": "Ruang kelas",
    "warna": {"lantai": "#dccfb8", "dinding": "#eef1ea", "samping": "#e6ece4", "plafon": "#f3f3ee", "list": "#c9bba2"},
    "langit": "#dfe8e4",
    "benda": [jendela_kiri(), jadwal, rak_rendah("3.4 0 -3.7", BUKU), meja_anak(), tanaman("-3.6 0 -3.5"),
              karpet("#cfe0d6")],
}

# ---------- 2. pintu kelas dan loker ----------
pintu = b("entity", position="-3.0 0 -3.97", anak=[
    b("plane", width=1.16, height=2.22, position="0 1.11 0", color="#b9a585"),
    b("plane", width=1.0, height=2.1, position="0 1.05 0.005", color="#d6c19d"),
    b("plane", width=0.36, height=0.5, position="0 1.62 0.01", color="#d4e8f0"),
    b("sphere", radius=0.04, position="0.38 1.0 0.04", color="#9a8a70"),
])
keset = b("plane", rotation="-90 0 0", width=1.1, height=0.6, position="-3.0 0.006 -3.4", color="#c7bba2")
loker_warna = ["#cfe0d6", "#e6d7b8", "#cdd9e6", "#e3d5cf"]
# loker di dinding belakang, kanan papan kartu
loker = b("entity", position="3.35 0 -3.78", anak=[
    b("box", width=1.7, height=1.25, depth=0.38, position="0 0.625 0", color="#c8b394"),
    *[b("box", width=0.48, height=0.52, depth=0.02, position=f"{-0.55 + kol * 0.55:.2f} {0.35 + bar * 0.58:.2f} 0.2",
        color=loker_warna[(kol + bar) % 4]) for kol in range(3) for bar in range(2)],
    # tas di atas loker
    b("box", width=0.34, height=0.38, depth=0.18, position="0.4 1.44 0", color="#9fb7c9"),
])
gantungan = b("entity", position="-4.47 1.5 -0.6", rotation="0 90 0", anak=[
    b("plane", width=1.4, height=0.12, color="#c8b394"),
    *[b("sphere", radius=0.035, position=f"{x} 0 0.03", color="#9a8a70") for x in (-0.5, -0.17, 0.17, 0.5)],
])
PINTU = {
    "nama": "Pintu kelas dan loker",
    "warna": {"lantai": "#dccfb8", "dinding": "#ecefe6", "samping": "#e5eae2", "plafon": "#f3f3ee", "list": "#c9bba2"},
    "langit": "#dfe8e4",
    "benda": [pintu, keset, loker, gantungan, tanaman("3.6 0 -0.4"), karpet("#cfe0d6")],
}

# ---------- 3. wastafel kelas ----------
garis_ubin = [b("plane", width=9, height=0.012, position=f"0 {y:.2f} -3.985", color="#c9d6d8")
              for y in (0.35, 0.65, 0.95, 1.25)]
wastafel = b("entity", position="-3.0 0 -3.7", anak=[
    b("box", width=1.4, height=0.78, depth=0.55, position="0 0.39 0", color="#d9dfe0"),
    b("box", width=1.46, height=0.05, depth=0.6, position="0 0.8 0", color="#eef2f2"),
    b("cylinder", radius=0.24, height=0.06, position="0 0.81 0.02", color="#c4d3d6"),
    b("cylinder", radius=0.025, height=0.26, position="0 0.95 -0.2", color="#a7b3b5"),
    b("cylinder", radius=0.02, height=0.16, position="0 1.07 -0.13", rotation="90 0 0", color="#a7b3b5"),
    b("box", width=0.09, height=0.18, depth=0.09, position="0.45 0.92 -0.12", color="#a9c4ad"),
])
cermin = b("entity", position="-3.0 1.65 -3.975", anak=[
    b("plane", width=0.9, height=0.7, color="#b9c4c4"),
    b("plane", width=0.82, height=0.62, position="0 0 0.005", color="#e3eef0"),
])
handuk = b("entity", position="-4.45 1.0 -2.6", rotation="0 90 0", anak=[
    b("cylinder", radius=0.015, height=0.7, rotation="0 0 90", position="0 0.32 0.04", color="#a7b3b5"),
    b("plane", width=0.5, height=0.62, position="0 0.02 0.05", color="#a9c4ad"),
])
bangku = b("box", width=0.5, height=0.18, depth=0.32, position="-3.0 0.09 -3.15", color="#c8d4cf")
WASTAFEL = {
    "nama": "Wastafel kelas",
    "warna": {"lantai": "#d7dbd8", "dinding": "#eaf1f1", "samping": "#e3ecec", "plafon": "#f3f5f4", "list": "#bfcac9"},
    "langit": "#dfe8e7",
    "benda": [*garis_ubin, wastafel, cermin, handuk, bangku, tanaman("3.6 0 -3.5"), karpet("#d5e3e3")],
}

# ---------- 4. area bermain ----------
matras = b("entity", position="1.0 0.006 -2.25", rotation="-90 0 0", anak=[
    b("plane", width=0.9, height=0.7, position=f"{x} {y} 0", color=c)
    for (x, y), c in zip([(-0.45, 0.35), (0.45, 0.35), (-0.45, -0.35), (0.45, -0.35)],
                         ["#d9e6dc", "#e8dcc2", "#d6e0ea", "#eadbd6"])
])
balok = b("entity", position="0.8 0 -2.2", anak=[
    b("box", width=0.16, height=0.16, depth=0.16, position="0 0.09 0", color="#9fb7c9"),
    b("box", width=0.16, height=0.16, depth=0.16, position="0 0.25 0", color="#c9b38a"),
    b("box", width=0.16, height=0.16, depth=0.16, position="0.35 0.09 0.05", color="#a9c4ad"),
])
kotak_mainan = [b("box", width=0.38, height=0.26, depth=0.28, position=f"{x} 1.03 0", color=c)
                for x, c in [(-0.45, "#cdd9e6"), (0.0, "#e6d7b8"), (0.45, "#cfe0d6")]]
bantal = b("entity", position="-3.3 0 -2.9", anak=[
    b("sphere", radius=0.36, scale="1 0.4 1", position="0 0.14 0", color="#d6c7b0"),
    b("sphere", radius=0.3, scale="1 0.4 1", position="0.6 0.12 0.35", color="#c8d6cc"),
])
BERMAIN = {
    "nama": "Area bermain",
    "warna": {"lantai": "#ddd0b9", "dinding": "#f0efe6", "samping": "#e9ebe1", "plafon": "#f4f3ee", "list": "#cbbda4"},
    "langit": "#e3e8e1",
    "benda": [jendela_kiri(), matras, balok, rak_rendah("3.4 0 -3.7", kotak_mainan), bantal,
              karpet("#cfe0d6")],
}

# ---------- 5. sudut tenang ----------
tenda = b("entity", position="-3.4 0 -3.2", anak=[
    b("cone", radius_bottom=0.75, radius_top=0.12, height=1.35, position="0 0.675 0", color="#b9cbc3"),
    b("plane", width=0.5, height=0.8, position="0.42 0.42 0.6", rotation="0 30 0", color="#8fa79d"),
    b("circle", rotation="-90 0 0", radius=0.85, position="0 0.008 0", color="#d8cfbf"),
])
pufpuf = b("sphere", radius=0.45, scale="1 0.55 1", position="2.6 0.25 -2.6", color="#b8c9c2")
mainan_lembut = [b("sphere", radius=0.13, position=f"{x} 1.03 0", color=c)
                 for x, c in [(-0.4, "#e3d5cf"), (0.05, "#cdd9e6"), (0.45, "#d9e6dc")]]
TENANG = {
    "nama": "Sudut tenang",
    "warna": {"lantai": "#d8cfc0", "dinding": "#e3ebe8", "samping": "#dde6e3", "plafon": "#eef1ef", "list": "#c2bcae"},
    "langit": "#dce4e1",
    "cahaya": {"ambien": 0.6, "arah": 0.35, "titik": 0.15},
    "benda": [tenda, pufpuf, rak_rendah("3.4 0 -3.7", mainan_lembut), karpet("#d4e0da", radius=1.2)],
}

DATA = {
    "catatan": "Dibuat oleh alat/latar/buat_latar.py. Latar dipilih otomatis dari peta_ta saat guru menekan MULAI, "
               "atau dipilih guru di dasbor. Posisi avatar dan papan kartu sama di semua latar.",
    "bawaan": "kelas",
    "peta_ta": {"TA-01": "pintu", "TA-02": "wastafel", "TA-03": "kelas", "TA-04": "kelas", "TA-05": "pintu",
                "TA-06": "kelas", "TA-07": "bermain", "TA-08": "kelas", "TA-09": "tenang", "TA-10": "kelas"},
    "dasar": DASAR,
    "latar": {"kelas": KELAS, "pintu": PINTU, "wastafel": WASTAFEL, "bermain": BERMAIN, "tenang": TENANG},
}

if __name__ == "__main__":
    KELUAR.parent.mkdir(parents=True, exist_ok=True)
    KELUAR.write_text(json.dumps(DATA, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{KELUAR}: {len(DATA['latar'])} latar")
