# Pipeline Development

How the pipeline is structured and how to extend it.

## Phase flow

```
preflight → scaffold → ingest → extract → analyze (agent) → assemble → verify
```

- `preflight` — environment/config checks
- `scaffold` — copies `skills/_template/` to `skills/<slug>/`
- `ingest` — lists raw source files in `source/<slug>/`
- `extract` — samples raw text, picks short excerpts, flags copyright risks
- `analyze` — **agent**: runs the writeprint generator, fills analysis + SKILL.md
- `assemble` — replaces remaining `{{placeholders}}`, validates output

The deterministic phases are runnable without a model — they are pure Python. `analyze` is the agent's reasoning step and is intentionally non-deterministic.

## Adding a phase

1. Add the phase name to `PHASES` in `run_pipeline.py`
2. Implement `phase_<name>(self, item)` returning `{"skip": bool, ...}`
3. Update the Phase Overview table in `SKILL.md`

## Conventions

- Deterministic work goes in `pipeline/scripts/` (Python)
- Non-deterministic work (writeprint, excerpt analysis, SKILL.md writing) is the agent's job
- State persists in `pipeline/state.json` (gitignored). Every phase must persist status via `self.state`
- The template in `skills/_template/` is the contract — `assemble` validates placeholders against it

## Testing

```bash
python -m pytest pipeline/tests/   # once tests exist
```

The fast check is a dry run with no sources — preflight should pass, and a run with an empty source dir should fail gracefully (no sources → flag, not crash).