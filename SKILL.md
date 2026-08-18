---
name: comedian-voice-generator
description: >
  Generates a comedian voice skill from raw source material. Runs the pipeline:
  ingest raw books/transcripts → extract short structural excerpts → run writeprint
  analysis → assemble SKILL.md + style-analysis.md into skills/<slug>/.
  Use when adding a new comedian to the comedian-voices repo, or when the user
  drops a book or transcript and asks to build a comedian voice from it.
---

# Comedian Voice Generator

Turns raw comedians' source material (books, stand-up special transcripts, interviews) into a loadable comedian voice skill: `SKILL.md` + `<slug>-style-analysis.md`, following the two-part pattern proven in `standup-skills/`.

The deterministic parts (folder scaffolding, slug/name validation, excerpt selection, templating, assembly, copyright checks) are Python scripts in `scripts/`. The analysis itself — extracting structural moves, rhetorical patterns, and the writeprint — is performed by the agent using the writeprint generator and its own judgment, because it is non-deterministic.

---

## Work Units

Each work unit = **one comedian**. Input = a directory of raw source files under `source/<slug>/`. Output = a complete `skills/<slug>/` skill folder.

## First-Time Setup

1. `python -m venv .venv && source .venv/bin/activate && pip install -r scripts/requirements.txt`
2. `cp config.example.json config.json` — adjust `source_dir`, `skills_dir`, and `model` settings.
3. Run `python -m scripts.preflight --config config.json` to verify the environment.

No external API keys are required — the analysis step runs in this agent, not via a separate service.

## File Structure

```
comedian-voices/
├── skills/
│   ├── _template/                  # reusable scaffold (SKILL.md + analysis + references/README.md)
│   └── <slug>/                    # generated skills (one per comedian)
│       ├── SKILL.md
│       └── <slug>-style-analysis.md
├── source/
│   └── <slug>/                   # raw source material — gitignored
├── writeprint/
│   └── writeprint-generator.md   # the analysis prompt used in step 3
└── pipeline/
    ├── SKILL.md                  # this file
    ├── config.example.json
    ├── scripts/
    │   ├── __init__.py
    │   ├── shared_utils.py       # env/config/validation
    │   ├── state_store.py        # JSON queue of comedians
    │   ├── session_logger.py     # JSONL audit trail
    │   ├── preflight.py          # Phase 0 environment check
    │   ├── transcribe.py         # standalone Whisper media→text transcriber
    │   ├── extractor.py          # short-excerpt extraction + copyright flagging
    │   └── run_pipeline.py       # main orchestrator
    └── references/
        ├── fair-use.md           # copyright policy (see skills/_template/references/README.md)
        └── development.md        # how to add/extend pipeline phases
```

## Config Template

```json
{
  "source_dir": "./source",
  "skills_dir": "./skills",
  "extraction": {
    "max_excerpts": 40,
    "excerpt_min_chars": 40,
    "excerpt_max_chars": 400,
    "samples_per_source": 12,
    "context_lines": 3
  },
  "analysis": {
    "max_excerpt_chars": 2400,
    "output_file": "{{slug}}-style-analysis.md"
  },
  "session": {
    "max_items_per_session": 3
  }
}
```

## Phase Overview

| Phase | Name | What it does |
|-------|------|--------------|
| 0 | preflight | Validates config, source dir, skills dir, template presence |
| 1 | scaffold | Creates `skills/<slug>/` from `_template/`, validates slug & name |
| 2 | ingest | Lists sources in `source/<slug>/`, computes stats, flags copyright-risk files |
| 3 | transcribe | Transcribes media in `source/<slug>/raw/` → `transcripts/` (skips if no media) |
| 4 | extract | Samples raw source → picks short structural excerpts (deterministic) |
| 5 | analyze | **Agent** — runs writeprint on excerpts, fills analysis + SKILL.md |
| 6 | assemble | Replaces `{{placeholders}}` in scaffold with real content, validates output |

Phases 0–4 are deterministic. Phase 4 (`analyze`) is the agent's reasoning step — the orchestrator stops there and the agent completes it. Phase 5 is the assembler script plus validation.

## Running

```bash
# Preflight only
python -m scripts.preflight --config config.example.json

# Scaffold + ingest + extract for one comedian (agent then does phase 4)
python -m scripts.run_pipeline --config config.example.json --item jerry-seinfield

# Assemble after the agent has written the analysis
python -m scripts.run_pipeline --config config.example.json --item jerry-seinfield --only assemble
```
## Transcribe (media → text)

Raw stand-up video/audio in `source/<slug>/raw/` is transcribed with the standalone Whisper tool before extraction:

```bash
# List media without running the model
python -m pipeline.scripts.transcribe --dry-run

# Transcribe a comedian's raw media into transcripts/
python -m pipeline.scripts.transcribe source/jerry-seinfield/raw --output-dir source/jerry-seinfield/transcripts
```

See `pipeline/scripts/INSTALL.md` (setup) and `DIARIZATION.md` (speaker labels). Transcripts stay under `source/` (gitignored) — only the distilled skill is committed.
## State Store Schema

`pipeline/state.json` (gitignored). Fields per item:

| Field | Type | Description |
|-------|------|-------------|
| id | string | comedian slug |
| name | string | display name |
| status | string | queued / scaffolded / extracted / analyzed / assembled / failed |
| source_dirs | list[str] | raw source paths |
| sources | list | ingested file stats |
| excerpts | list | extracted excerpts (with provenance) |
| output_dir | string | skills/<slug> |
| notes | string | free text |

## Status Codes

- `queued` — added, waiting
- `scaffolded` — folder + template copied
- `extracted` — excerpts chosen
- `analyzed` — agent wrote the analysis + SKILL.md
- `assembled` — placeholders replaced, validated (done)
- `failed` — error during deterministic phase

## Copyright Guard

`extractor.py` refuses to generate anything when a source file looks like a full book or full special (> ~50KB, or repeated page-marker noise). Instead it flags the file and asks for curated short excerpts. See `references/fair-use.md` and `skills/_template/references/README.md`.

## Error Recovery

| Error | Recovery |
|-------|----------|
| Slug invalid | Rename source dir; rerun preflight |
| Source file too large / full-work flags | Replace with curated short excerpts, rerun extract |
| `{{placeholder}}` tokens remain after assemble | Reopen SKILL.md, fill gaps, rerun assemble |
| Analysis incomplete | Rerun phase 4 (agent) before assemble |