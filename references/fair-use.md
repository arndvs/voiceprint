# Fair-Use & Copyright Policy

The comedian-voices repo is public and MIT-licensed. It is a **style-analysis corpus**, not a text reproduction repository.

## Hard rules

1. **Never commit full copyrighted works.** No full books, full specials, full albums, full transcripts.
2. **Quotes are evidence, not content.** A quote exists only to evidence a *pattern* the analysis describes. If the pattern can be explained without the quote, drop the quote.
3. **Excerpts are short.** A few lines per excerpt. Never a full bit, never a full chapter, never a full routine.
4. **Excerpts are sparsely distributed.** A whole book of bits is not a corpus — it's a reproduction. You may quote scattered representative lines, never a sustained passage or the bulk of any work.
5. **Analysis always precedes and explains every quote.** The value is in the distilled style analysis. Prose must never be a wrapper around quoted text.
6. **Always attribute.** Source title, year, venue/medium. If you don't know where a quote came from, don't include it.

## How the pipeline enforces this

The raw material the user provides (`source/<slug>/`) is **gitignored** — it stays local. What gets committed is the output skill, which quotes only scattered structural micro-examples.

The extractor (`scripts/extractor.py`) refuses to generate anything from a file that looks like a full work:

- Media files (audio/video) — flagged, must be transcribed to text first
- Front matter with copyright/ISBN block — flagged as a published book
- Full-length raw text (> 120k chars) — flagged
- High page-marker noise — flagged as a scanned book

When a file is flagged, the pipeline stops and asks for curated short excerpts instead of the full work.

## When in doubt

Quote less, analyze more. If a reviewer could reconstruct the bulk of a work from this repo, it is a violation even if every quote is short.