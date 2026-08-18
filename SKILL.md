---
name: voice-generator
description: >
  Generates a writing-style voice skill from raw source material. Runs the
  pipeline: ingest raw books/transcripts → extract short structural excerpts →
  run writeprint analysis → assemble SKILL.md + analysis.md into skills/<slug>/.
  Use to create a loadable voice skill for any writer — a comedian, an author,
  a founder, or your own writing style.
---

# Voice Style Generator

Turns raw source material (books, transcripts, emails, your own writing) into a loadable writing-style skill: `SKILL.md` + `<slug>-analysis.md`, following the two-part pattern: a deep source analysis + a distilled, agent-loadable skill.

The deterministic parts (folder scaffolding, slug validation, excerpt selection, templating, assembly, copyright checks) are Python scripts in `scripts/`. The analysis itself — extracting tone, register, syntax, and idiosyncratic moves — is performed by the agent using the writeprint generator, because it is non-deterministic.

> **Content packs** — for a ready-made set of curated comedian voice skills, see [arndvs/comedian-voices](https://github.com/arndvs/comedian-voices). That repo ships skills only (no pipeline code); generate new ones here and PR them there.

---

## Work Units

Each work unit = **one voice**. Input = a directory of raw source files under `source/<slug>/`. Output = a complete `skills/<slug>/` skill folder (or emit into a content-pack checkout with `--emit-to`).

## First-Time Setup

1. `python -m venv .venv && source .venv/bin/activate && pip install -r scripts/requirements.txt`
2. `cp config.example.json config.json` — adjust `template_type` (`comedian` | `author` | `personal`), `source_dir`, `skills_dir`, and settings.
3. Run `python -m scripts.preflight --config config.json` to verify the environment.

No external API keys are required — the analysis step runs in the agent, not via a separate service. (Transcription needs Whisper; see `scripts/INSTALL.md`.)

## File Structure

```
voiceprint/
├── config.example.json      # template_type selects the scaffold (comedian/author/personal)
├── templates.registry.json  # template_type → template dir + output contract
├── pyproject.toml
├── scripts/
│   ├── __init__.py
│   ├── shared_utils.py       # env/config/validation + templates registry
│   ├── state_store.py        # JSON queue of voices
│   ├── session_logger.py     # JSONL audit trail
│   ├── preflight.py          # Phase 0 environment check
│   ├── transcribe.py         # standalone Whisper media→text transcriber
│   ├── extractor.py          # short-excerpt extraction + copyright flagging
│   ├── assembler.py          # placeholder replacement + output validation
│   └── run_pipeline.py       # main orchestrator
├── templates/
│   ├── comedian/             # SKILL.md + <slug>-style-analysis.md
│   ├── author/               # same two-file shape, writing (not comedy) vocabulary
│   └── personal/             # personal-register voice
├── writeprint/
│   └── writeprint-generator.md  # the analysis prompt used in step 3
├── references/
│   ├── fair-use.md           # copyright policy
│   └── development.md        # how to add/extend pipeline phases
└── source/                   # raw material — gitignored (never commit full works)
```

## Template Types

The scaffold for `skills/<slug>/` comes from `templates/<type>/`, chosen by the
`template_type` key in `config.json`. The mapping `template_type → template dir`
(and the expected output shape) lives in `templates.registry.json`.

- `comedian` — stand-up voice: comedic architecture, bit structure, callback tags.
- `author` — prose voice: writing architecture, rhetorical moves, essay structure.
- `personal` — your own (or a founder's) register: signature moves, subjects/energy, boundaries.

Every type emits the same two-file contract: `SKILL.md` + `<slug>-style-analysis.md`.

## The Two-Part Output

Every generated skill in `skills/<slug>/` has two files:

- **`<slug>-style-analysis.md`** — the deep source analysis: tone, architecture, mechanics, rhetorical moves, fingerprints, themes, anti-patterns, excerpt index.
- **`SKILL.md`** — the concise, loadable version agents apply immediately.

Both carry `skill_version: 1` frontmatter.

## Phase Overview

| Phase | Name | What it does |
|-------|------|--------------|
| 0 | preflight | Validates config, source dir, skills dir, template presence |
| 1 | scaffold | Creates `skills/<slug>/` from the template |
| 2 | ingest | Lists sources in `source/<slug>/`, computes stats, flags copyright-risk files |
| 3 | transcribe | (Optional) Whisper media → `transcripts/` |
| 4 | extract | Samples raw source → short excerpts (deterministic) |
| 5 | analyze | **Agent** — runs writeprint on excerpts, fills analysis + SKILL.md |
| 6 | assemble | Replaces `{{placeholders}}` in scaffold, validates output |

Phases 0–5 are deterministic. Phase 5 (`analyze`) is the agent's reasoning step — the orchestrator stops for it. Phase 6 is the assembler + validation.

## Running

```bash
# Preflight only
python -m scripts.preflight --config config.example.json

# Scaffold + ingest + transcribe + extract for one voice (agent then does analyze)
python -m scripts.run_pipeline --config config.example.json --item <slug>

# Assemble after the agent has written the analysis
python -m scripts.run_pipeline --config config.example.json --item <slug> --only assemble
```

## Copyright Guard

`extractor.py` refuses to generate anything when a source file looks like a full work (>120k chars, or a published-book front matter block). It flags the file and asks for curated short excerpts. This repo ships analysis, not reproductions — see `references/fair-use.md`.

## Error Recovery

| Error | Recovery |
|-------|----------|
| Slug invalid | Rename source dir; rerun preflight |
| Source file too large / full-work flags | Replace with curated short excerpts, rerun extract |
| `{{placeholder}}` tokens remain after assemble | Reopen SKILL.md, fill gaps, rerun assemble |
| Analysis incomplete | Rerun phase 5 (agent) before assemble |
