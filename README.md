# asd-tutor

A guarded retrieval-augmented tutor agent for children with autism in a supervised one-teacher-one-child
metaverse classroom. The language model selects and sequences instruction; it does not author what the
child hears. Every sentence spoken to the child must match a validated corpus, or it is blocked and the
teacher is called.

This repository accompanies the manuscript *A guarded RAG tutor agent for children with autism*
(Husaein, Krismiyati, Sembiring & Wellem, 2026, in preparation). Documentation inside the code and the
detailed guide (`PANDUAN.md`) are in Indonesian.

> **Not for use with children** without ethics approval, informed parental consent, expert-validated
> content (`ASD_RAG_MODE=prod`) and continuous one-to-one teacher supervision.

## Components

| Part | Files | Role |
|---|---|---|
| MCP server | `server.py`, `korpus_lib.py`, `ingest.py` | Five tools for the Hermes Agent tutor profile: `ambil_task_analysis` (verbatim by ID), `cari_strategi` (hybrid retrieval), `profil_anak`, `catat_langkah` (step scores for single-case research), `panggil_guru` |
| Corpus | `korpus/` | Ten task analyses (Indonesian), a 58-sentence speech bank, two strategies; YAML with validation status |
| Output guard | `penjaga.py` | Deterministic whitelist check of every tutor reply against the corpus after profile placeholders are filled |
| Bridge | `jembatan.py`, `hermes_klien.py`, `PROTOKOL_JEMBATAN.md` | WebSocket bridge between the teacher dashboard, the metaverse client and the Hermes API server |
| Teacher dashboard | `static/guru.html` | Start/stop sessions, approve steps, choose the room, see blocked replies and escalations |
| Metaverse client | `static/metaverse.html`, `static/aset/` | A-Frame classroom with a speaking avatar, picture-card board and five rooms |
| Tutor profile | `tutor_profile/` | Hermes profile setup, system prompt (`SOUL.md`), 13 behavioural test scenarios |
| Deployment | `deploy/` | systemd units, Caddy (HTTPS), SSH hardening templates |
| Tools | `kartu.py`, `rekap_ssr.py`, `eval_retrieval.py`, `validate_korpus.py` | Picture-card management, single-case data summary, retrieval evaluation, corpus checks |

## Quick start (development mode, no children)

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python validate_korpus.py
ASD_RAG_MODE=dev ./venv/bin/python ingest.py

# tests (no Hermes, no API key needed)
./venv/bin/python tests/test_penjaga.py
./venv/bin/python tests/test_jembatan.py
./venv/bin/python tests/test_hermes_klien.py

# bridge with a scripted fake tutor, then open http://127.0.0.1:8765/guru and /metaverse
JEMBATAN_PENGGERAK=palsu ASD_RAG_MODE=dev ./venv/bin/python jembatan.py
```

Running the real tutor needs Hermes Agent and an Anthropic API key; see `tutor_profile/README.md` and
`PANDUAN.md`. The MCP server requires `mcp` 1.x.

## Data and privacy

- `data/profil.json` holds one **synthetic** test profile (`A01`, `"uji": true`). Real learner profiles,
  session logs and tokens are written to `data/` on the server and are excluded by `.gitignore`.
  Do not commit real profiles.
- Development mode accepts only profiles marked `"uji": true`. Production mode loads only entries with
  `status: valid` and their expert-validation record.
- No data from children are included in this repository.

## Licences

- Source code: MIT (`LICENSE`).
- Corpus (`korpus/`): CC BY 4.0 (`korpus/LICENSE.md`).
- Third-party assets (A-Frame, avatar model) and project pictograms: see `ATTRIBUTION.md`.
- ARASAAC pictograms used in the study are downloaded by `kartu.py` and are not redistributed here
  (CC BY-NC-SA 4.0, Sergio Palao, ARASAAC, Government of Aragón).

## Citation

Husaein, A., Krismiyati, Sembiring, I., & Wellem, T. (2026). *asd-tutor: a guarded RAG tutor agent for
children with autism* [Computer software]. https://github.com/hu543in/asd-tutor
