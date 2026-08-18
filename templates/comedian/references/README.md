# Fair-Use & Copyright Policy

This repo is public and MIT-licensed. It is a **style-analysis corpus**, not a text reproduction repository. Every file that quotes a comedian's words must follow this policy.

## Hard rules

1. **Never commit full copyrighted works.** No full books, full specials, full albums, or full transcripts.
2. **Quotes are evidence, not content.** A quote exists only to evidence a *pattern* the analysis describes. If the pattern can be explained without the quote, drop the quote.
3. **Excerpts are short.** A few lines per excerpt. Never a full bit, never a full chapter, never a full routine.
4. **Excerpts are sparsely distributed.** A whole book of bits is not a corpus — it's a reproduction. You may quote scattered representative lines, never a sustained passage or the bulk of any work.
5. **Analysis always precedes and explains every quote.** The value of this repo is the distilled style analysis. Prose must never be a wrapper around quoted text; quotes are evidence inside original analysis.
6. **Always attribute.** Source title, year, venue/medium. If you don't know exactly where a quote came from, don't include it.

## Pipeline enforcement

The generation pipeline (see `scripts/`) defaults to **analysis-only output**: it instructs the model to quote only scattered structural micro-examples and to flag any source document that looks like a full book or full special. If a full work is detected in `source/raw/`, the pipeline refuses to generate until the raw file is replaced with selected, short excerpts or a pointer to the original.

## When in doubt

Quote less, analyze more. The value of this repo is the **distilled writeprint** — not the source text. If a reviewer could reconstruct the bulk of a work from this repo, it is a violation even if every quote is short.
