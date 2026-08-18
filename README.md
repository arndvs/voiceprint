# Voiceprint — Voice Style Generator

Turns raw source material (books, transcripts, interviews, **your own writing**) into a loadable writing-style skill. Each generated skill codifies the structural moves, rhetorical patterns, and anti-patterns of a voice — so an agent can write *in that voice*, not just imitate its surface jokes.

The pipeline: **transcribe → ingest → extract → writeprint analysis → assemble** → a two-part skill (`SKILL.md` + `<slug>-analysis.md`) you drop into your agent.

## Content pack

For a ready-made library of curated **comedian voice skills**, see:

- **[arndvs/comedian-voices](https://github.com/arndvs/comedian-voices)** — pre-built skills (no pipeline code). Clone it and drop `skills/` into your agent, or use this generator's `--emit-to` to generate new skills directly into a checkout of it.

## Example: generate a voice

```
source/<slug>/          # raw material (gitignored, stays local)
      │
      ▼
scripts/run_pipeline.py  # ingress → extract → analyze (agent) → assemble
      │
      ▼
skills/<slug>/           # SKILL.md + <slug>-analysis.md  (the loadable skill)
```

```bash
python -m scripts.transcribe source/<slug>/raw --output-dir source/<slug>/transcripts   # optional: video/audio
python -m scripts.run_pipeline --config config.example.json --item <slug>
```

The analysis step is agent-driven: it runs the writeprint generator against the extracted excerpts and fills the skill's sections. See `SKILL.md` for the full phase overview.

**Copyright:** raw books/transcripts stay local (`source/` is gitignored). The pipeline flags full works (>120k chars) and refuses to generate from them; only short, attributed excerpts ever land in a committed skill. See `references/fair-use.md`.

## Dev

```bash
pip install -r scripts/requirements.txt requirements-dev.txt
python -m pytest tests/
```

## License

MIT.
