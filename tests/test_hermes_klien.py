"""Uji pembaca jawaban API server Hermes dengan bentuk asli dari server (27 Okt 2026).
Jalankan:  ./venv/bin/python tests/test_hermes_klien.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hermes_klien import tool_aktif, urai_respons  # noqa: E402

JAWAB = json.dumps({"pujian": "", "ucap": "Buka keran.", "kartu": "Tangan memutar keran", "aksi": "tunggu",
                    "ta": "TA-02", "langkah": 1, "catatan_guru": ""})
RESPONS = {"id": "resp_x", "object": "response", "status": "completed", "output": [
    {"type": "function_call", "status": "completed", "name": "tool_describe",
     "arguments": json.dumps({"names": ["mcp__asd_rag__profil_anak", "mcp__asd_rag__ambil_task_analysis"]})},
    {"type": "function_call_output", "output": "{\"tools\": {}}"},
    {"type": "function_call", "status": "completed", "name": "tool_call",
     "arguments": json.dumps({"calls": [{"name": "mcp__asd_rag__profil_anak", "arguments": {"id_anak": "A01"}}]})},
    {"type": "function_call", "status": "completed", "name": "tool_call",
     "arguments": json.dumps({"calls": [{"name": "mcp__asd_rag__ambil_task_analysis",
                                         "arguments": {"id_ta": "TA-02", "id_anak": "A01"}}]})},
    {"type": "function_call_output", "output": "<untrusted_tool_result ...>"},
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": JAWAB}]},
]}
KATALOG = {"object": "list", "platform": "api_server", "data": [
    {"name": "terminal", "enabled": False, "configured": True, "tools": [{"name": "terminal"}, {"name": "process_manage"}]},
    {"name": "file", "enabled": False, "configured": True, "tools": ["read_file", "write_file"]},
]}

ok = []


def cek(nama, kondisi, info=""):
    ok.append(bool(kondisi))
    print(f"{'OK   ' if kondisi else 'GAGAL'} {nama}" + ("" if kondisi else f"\n      {info}"))


teks, alat = urai_respons(RESPONS)
cek("teks jawaban terbaca", json.loads(teks)["ucap"] == "Buka keran.", teks)
cek("tool_describe diabaikan", not any("describe" in a for a in alat), alat)
cek("tool_call {calls:[...]} dibuka", alat == ["mcp__asd_rag__profil_anak", "mcp__asd_rag__ambil_task_analysis"], alat)
gabung = {"output": [{"type": "function_call", "name": "tool_call", "arguments": json.dumps(
    {"calls": [{"name": "mcp__asd_rag__catat_langkah"}, {"name": "mcp__asd_rag__panggil_guru"}]})}]}
cek("satu tool_call berisi dua panggilan", urai_respons(gabung)[1] == ["mcp__asd_rag__catat_langkah",
                                                                      "mcp__asd_rag__panggil_guru"])
cek("tool bawaan langsung terbaca", urai_respons({"output": [{"type": "function_call", "name": "terminal",
                                                              "arguments": "{}"}]})[1] == ["terminal"])
cek("katalog: toolset nonaktif tidak dihitung", tool_aktif(KATALOG) == [])
KATALOG["data"][0]["enabled"] = True
cek("katalog: toolset aktif dihitung", tool_aktif(KATALOG) == ["process_manage", "terminal"], tool_aktif(KATALOG))
del KATALOG["data"][1]["enabled"]
cek("katalog: tanpa tanda enabled dianggap aktif", "read_file" in tool_aktif(KATALOG))
print(f"\n{sum(ok)} dari {len(ok)} lulus")
sys.exit(0 if all(ok) else 1)
