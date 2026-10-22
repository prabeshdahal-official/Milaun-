# Architecture

## Pipeline

```
raw name
  -> normalize        NFC, invisible marks, Devanagari digits, punctuation, case
  -> script dispatch  Devanagari state machine | Latin rule transcriber
  -> phonetic stream  canonical symbols (K G C J T D N P B M Y R L S H A I U E O)
  -> two keys         vowel-bearing key  +  consonant skeleton
  -> pair features    8 similarities
  -> logistic score   IRLS, ridge, non-negative weights
  -> calibration      Platt scaling fitted on a held-out split
  -> decision band    match / review / distinct
```

## Module boundaries

| Module | Depends on | Responsibility |
|---|---|---|
| `charset` | — | Unicode tables, canonical alphabet |
| `normalize` | `charset` | Text normalisation, script detection |
| `devanagari` | `charset`, `normalize` | One state machine → phonetic stream + readable Latin |
| `latin` | `charset`, `normalize` | Ordered romanisation rules |
| `phonetic` | `devanagari`, `latin` | Token reduction, diphthong folding, schwa deletion, keys |
| `similarity` | `phonetic` | Comparators and pair features |
| `blocking` | `phonetic` | Prefix inverted index, completeness metric |
| `model` | `similarity` | Feature weights, training, JSON persistence |
| `calibration` | — | Platt / isotonic, ECE, Brier, persistence |
| `matcher` | all of the above | Public API, bands, clustering, linking |
| `store`, `privacy` | — | Audit trail, pseudonyms, CSV guards |
| `cli`, `api`, `web` | `matcher` | Interfaces only; no matching logic |

The dependency graph is acyclic and points inward: interfaces depend on the matcher, never
the reverse. `matcher` is the only module that knows about thresholds.

## Key design decisions

**1. Two projections instead of one key.**
A single key cannot serve both precision and recall: the vowel-bearing key separates
`Prabesh`/`Prabin`, while the consonant skeleton absorbs epenthetic schwa
(`सापकोटा` → `SPKT` = `Sapkota`). Both are computed from the same event stream, and the
scorer learns how much to trust each. Cost: two extra features and a slightly larger
model; benefit: the two dominant error classes are handled by construction.

**2. Rules, not a learned transliterator.**
A seq2seq transliterator needs parallel data that does not exist openly for Nepali names,
and would be undebuggable for a records officer. Rules are inspectable, deterministic,
testable and free. Cost: rare spellings that break the rules rely on similarity features.

**3. Six-plus-two features and logistic regression, not a GBM.**
With a few thousand synthetic pairs, a gradient-boosted model would memorise the generator.
A linear model with non-negative weights keeps each explanation meaningful ("the family-name
token matches"). Cost: some interaction effects are missed.

**4. Non-negativity as a monotonicity prior.**
All features are similarities, so higher must never mean less likely. IRLS is projected onto
the non-negative orthant; without it, collinear features drove weights negative and the
per-pair explanations contradicted the score.

**5. Thresholds are policy, not fitted parameters.**
0.90 / 0.55 are fixed and documented. `train.py` reports what they cost on calibration data
and warns if precision falls below 0.98, instead of tuning them until the numbers look good.

**6. Blocking keeps recall visible.**
Three-character prefix keys per token plus skeleton prefixes. The reduction ratio *and*
pair completeness are both reported, because blocking recall cannot be recovered downstream.

## Storage and interfaces

- **Audit store**: SQLite, append-only runs/pairs, schema-version guard, no name column.
- **CLI**: `argparse`, exit code 2 for input errors, `--json` on every command.
- **HTTP**: FastAPI, loopback by default, request caps, security headers, no request logging.
- **UI**: one static HTML file, no external assets, `aria-live` results, keyboard operable.

## Deployment

Single machine, `pip install -e ".[web]"`, no external services. The core has zero runtime
dependencies, so it also runs from a copied `src/` tree on an air-gapped laptop.

## Failure modes considered

| Failure | Handling |
|---|---|
| Empty or numeric-only name | Empty keys → features 0 → low score, no exception |
| Very long field | Pydantic `max_length=200`; CLI row cap 200k |
| Corrupt CSV / wrong column | Explicit error message, exit code 2 |
| Missing packaged model | Falls back to documented default weights |
| Newer audit schema | Refuses to open, tells the user to upgrade |
| Spreadsheet formula injection | Prefix `'` on `= + - @ tab CR` |

## Performance envelope

Measured by `benchmarks/evaluate.py` on one core (see `benchmarks/results/RESULTS.md`):
sub-millisecond per pair, low hundreds of KiB for a 180-record clustering run. Blocking is
the scaling lever; pairwise scoring is linear in the number of candidates.
