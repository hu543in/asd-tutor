"""Kunci profil Hermes 'tutor-asd' agar hanya bisa memakai tool asd_rag.

Jalankan SETELAH `hermes profile create tutor-asd`:
    ~/asd-rag/venv/bin/python ~/asd-rag/tutor_profile/setup_tutor_profile.py

Yang dilakukan:
  1. Cadangkan config.yaml profil.
  2. Model: Anthropic, claude-sonnet-5-5.
  3. Tool: platform_toolsets.cli = [asd_rag] dan semua toolset bawaan dimatikan
     (terminal, file, web, browser, memory, skills, eksekusi kode, delegasi, dll.).
  4. skills.write_approval = true (agen tidak bisa menulis skill tanpa persetujuan).
  5. Salin SOUL.md tutor ke profil.
  6. .env profil berisi ANTHROPIC_API_KEY (disalin dari profil default jika belum ada).
  7. (v6) API server Hermes untuk jembatan metaverse: hanya 127.0.0.1:8643, kunci acak di .env,
     dan platform_toolsets.api_server = [asd_rag]; gateway.standalone = true.
  8. (v7.2) Tutor hanya diberi empat tool asd_rag; cari_strategi tidak termasuk.
  9. (v7.3) panggil_guru dikirim ke jembatan (ASD_RAG_WEBHOOK), tampil langsung di dasbor guru.
"""
import re
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

PROFIL = "tutor-asd"
PORT_API = 8643
TOOL_TUTOR = ["ambil_task_analysis", "profil_anak", "catat_langkah", "panggil_guru"]
HERMES = Path.home() / ".hermes"
PDIR = HERMES / "profiles" / PROFIL
SINI = Path(__file__).resolve().parent
ASD_HOME = SINI.parent

DIMATIKAN = [
    "browser", "clarify", "code_execution", "connections", "computer_use", "cronjob", "delegation",
    "desktop_ui", "discord", "discord_admin", "feishu_doc", "feishu_drive", "file", "image_gen",
    "kanban", "memory", "project", "catalog", "search", "session_search", "skills", "terminal",
    "todo", "tts", "video", "video_gen", "vision", "web", "x_search", "yuanbao",
]


def blok_asd_rag() -> dict:
    """Ambil blok asd_rag dari config profil default agar setelan (model, ambang) sama."""
    try:
        cfg = yaml.safe_load((HERMES / "config.yaml").read_text()) or {}
        blok = (cfg.get("mcp_servers") or {}).get("asd_rag")
        if blok:
            return blok
    except Exception:
        pass
    return {
        "command": str(ASD_HOME / "venv/bin/python"),
        "args": [str(ASD_HOME / "server.py")],
        "env": {"ASD_RAG_HOME": str(ASD_HOME), "ASD_RAG_MODE": "dev",
                "ASD_RAG_EMBED_MODEL": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
                "ASD_RAG_T_SEM": "0.52", "ASD_RAG_T_KATA": "0.26"},
        "timeout": 60, "connect_timeout": 120,
        "tools": {"include": ["ambil_task_analysis", "cari_strategi", "profil_anak", "catat_langkah",
                              "panggil_guru"], "prompts": False, "resources": False},
    }


def main() -> int:
    if not PDIR.exists():
        print(f"Profil belum ada: {PDIR}\nJalankan dulu:  hermes profile create {PROFIL}")
        return 1

    cfg_path = PDIR / "config.yaml"
    teks = cfg_path.read_text() if cfg_path.exists() else ""
    for kunci in set(re.findall(r"^([A-Za-z_]+):", teks, flags=re.M)):
        if len(re.findall(rf"^{kunci}:", teks, flags=re.M)) > 1:
            print(f"config.yaml profil berisi kunci ganda '{kunci}'. Perbaiki dulu sebelum melanjutkan.")
            return 1
    if cfg_path.exists():
        cadangan = cfg_path.with_name(f"config.yaml.sebelum-tutor-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(cfg_path, cadangan)
        print(f"Cadangan: {cadangan}")
    cfg = yaml.safe_load(teks) or {}

    model = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    model.update({"provider": "anthropic", "default": "claude-sonnet-5-5"})
    cfg["model"] = model

    blok = blok_asd_rag()
    # Tutor hanya butuh empat tool. cari_strategi (pencarian vektor, model ~1 GB) untuk guru/pengembang.
    blok["tools"] = {"include": TOOL_TUTOR, "prompts": False, "resources": False}
    (blok.get("env") or {}).pop("ASD_RAG_PEMANASAN", None)
    # panggil_guru diteruskan ke dasbor guru lewat jembatan (v7.3)
    blok.setdefault("env", {})["ASD_RAG_WEBHOOK"] = "http://127.0.0.1:8765/internal/panggil_guru"
    cfg["mcp_servers"] = {"asd_rag": blok}  # hanya asd_rag, tidak ada server MCP lain

    pt = cfg.get("platform_toolsets") or {}
    pt["cli"] = ["asd_rag"]
    pt["api_server"] = ["asd_rag"]   # jembatan metaverse memakai API server
    cfg["platform_toolsets"] = pt

    agent = cfg.get("agent") or {}
    agent["disabled_toolsets"] = sorted(set(agent.get("disabled_toolsets") or []) | set(DIMATIKAN))
    cfg["agent"] = agent

    gw = cfg.get("gateway") or {}
    api = gw.get("api_server") or {}
    api.update({"enabled": True, "host": "127.0.0.1", "port": PORT_API})
    gw["api_server"] = api
    # Hermes 0.21 menolak gateway per profil kecuali standalone; profil tutor sengaja dipisah dari
    # gateway profil pengembang agar tool dan kuncinya tidak tercampur.
    gw["standalone"] = True
    cfg["gateway"] = gw

    skills = cfg.get("skills") or {}
    skills["write_approval"] = True
    skills["guard_agent_created"] = True
    cfg["skills"] = skills

    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
    print(f"config.yaml profil diperbarui: {cfg_path}")

    shutil.copy2(SINI / "SOUL.md", PDIR / "SOUL.md")
    print(f"SOUL.md tutor disalin ke {PDIR / 'SOUL.md'}")

    env_p = PDIR / ".env"
    env_teks = env_p.read_text() if env_p.exists() else ""
    if "ANTHROPIC_API_KEY=" not in env_teks:
        sumber = (HERMES / ".env").read_text() if (HERMES / ".env").exists() else ""
        baris = [b for b in sumber.splitlines() if b.startswith("ANTHROPIC_API_KEY=")]
        if baris:
            env_p.write_text(baris[0] + "\n")
            env_p.chmod(0o600)
            print("ANTHROPIC_API_KEY disalin ke .env profil (hanya kunci ini).")
        else:
            print("PERHATIAN: ANTHROPIC_API_KEY tidak ditemukan. Jalankan: hermes -p tutor-asd model")
    env_teks = env_p.read_text() if env_p.exists() else ""
    tambahan = []
    if "API_SERVER_ENABLED=" not in env_teks:
        tambahan.append("API_SERVER_ENABLED=true")
    if "API_SERVER_PORT=" not in env_teks:
        tambahan.append(f"API_SERVER_PORT={PORT_API}")
    if "API_SERVER_KEY=" not in env_teks:
        tambahan.append(f"API_SERVER_KEY={secrets.token_urlsafe(24)}")
    if tambahan:
        with open(env_p, "a") as f:
            f.write(("" if env_teks.endswith("\n") or not env_teks else "\n") + "\n".join(tambahan) + "\n")
        env_p.chmod(0o600)
        print(f"API server tutor diaktifkan di .env profil ({', '.join(t.split('=')[0] for t in tambahan)}).")
    print("\nSelesai. Periksa dengan:\n  hermes -p tutor-asd config check\n  hermes -p tutor-asd mcp test asd_rag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
