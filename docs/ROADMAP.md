# Roadmap

Ordered by what most increases the project's credibility, not by what is easiest.

## v0.1 — released

- [x] Devanagari + Latin phonetic projection with consonant skeleton
- [x] Pair features, IRLS logistic scorer, Platt calibration
- [x] Blocking index with measured pair completeness
- [x] Three-band triage and cost-sensitive decision rule
- [x] CLI (`compare`, `key`, `dedupe`, `link`, `serve`, `pseudonymize`)
- [x] Local HTTP API and accessible review UI
- [x] Audit store without a name column; HMAC pseudonyms; CSV injection guard
- [x] Test suite, reproducible benchmark, CI

## v0.2 — evidence

- [ ] **Hand-labelled real-world evaluation set.** A few thousand consented, de-identified
      record pairs from at least one clinic and one cooperative, two annotators, Cohen's κ
      reported. This is the single most valuable contribution anyone can make.
- [ ] Publish a calibration report per deployment, not only for the synthetic benchmark.
- [ ] Error taxonomy of real failures (nicknames, clan names, honorifics, spelling
      conventions by region).

## v0.3 — linkage quality

- [ ] Composite records: date of birth, ward/district, guardian name, with per-field
      comparators and a Fellegi–Sunter style model instead of name-only features.
- [ ] Better handling of dropped middles and initials (currently a known weak case).
- [ ] Optional learned transliteration for out-of-rule spellings, shipped as an optional extra
      so the core stays dependency-free.
- [ ] Transitive-closure guards for clustering (min-link / correlation clustering) to prevent
      chained false merges.

## v0.4 — operations

- [ ] Nepali-language UI strings and Devanagari-first typography.
- [ ] Review-queue export with stable ordering and reviewer assignment.
- [ ] Streaming mode for very large CSVs with a disk-backed blocking index.
- [ ] Signed model artefacts and a documented retraining procedure for partners.

## Explicitly not planned

- A hosted service or SaaS.
- Face, fingerprint or any biometric matching.
- Internet-facing deployment without a separate security review.
- Claiming accuracy on languages that have not been evaluated.
