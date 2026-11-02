"""Tampilkan isi model avatar GLB: ukuran, nama animasi, dan morph target untuk gerak mulut.

Pemakaian:  python periksa_avatar.py static/aset/avatar/guru.glb
Hanya memakai pustaka standar Python (membaca bagian JSON di dalam file GLB).
"""
import json
import struct
import sys
from pathlib import Path


def baca_glb(path: Path) -> dict:
    data = path.read_bytes()
    magic, versi, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise SystemExit("Bukan file GLB (glTF biner).")
    panjang, jenis = struct.unpack_from("<I4s", data, 12)
    if jenis != b"JSON":
        raise SystemExit("Bagian JSON tidak ditemukan.")
    return json.loads(data[20:20 + panjang])


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    p = Path(sys.argv[1])
    g = baca_glb(p)
    print(f"File       : {p.name} ({p.stat().st_size / 1e6:.1f} MB)")
    info = (g.get("asset") or {}).get("extras") or {}
    for k in ("title", "author", "license", "source"):
        if info.get(k):
            print(f"{k.capitalize():11}: {info[k]}")
    ekstensi = g.get("extensionsRequired", [])
    print(f"Ekstensi   : {', '.join(g.get('extensionsUsed', [])) or '-'}")
    if "KHR_materials_pbrSpecularGlossiness" in g.get("extensionsUsed", []):
        print("PERINGATAN : material spec-gloss tidak didukung three.js versi sekarang (model tampil tanpa warna). Konversi:")
        print("             npx @gltf-transform/cli metalrough masukan.glb guru.glb")
    if any(e in ekstensi for e in ("KHR_draco_mesh_compression", "EXT_meshopt_compression")):
        print("PERINGATAN : model memakai kompresi Draco/meshopt; klien belum memuat dekodernya. Ekspor ulang tanpa kompresi.")
    print("Animasi    :", ", ".join(a.get("name", "(tanpa nama)") for a in g.get("animations", [])) or "tidak ada")
    morf = sorted({n for m in g.get("meshes", []) for n in (m.get("extras") or {}).get("targetNames", [])})
    print("Morph      :", ", ".join(morf) or "tidak ada (mulut tidak bergerak; avatar tetap bisa dipakai)")
    if not morf:
        nama = [n.get("name") for n in g.get("nodes", []) if "mesh" in n and n.get("name")]
        print("Bagian     :", ", ".join(nama[:30]), "(isi mulutOverlay.mesh dengan bagian mulut/gigi bila ada)")
    if p.stat().st_size > 15e6:
        print("PERINGATAN : file lebih dari 15 MB; tablet sekolah bisa lambat memuatnya.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
