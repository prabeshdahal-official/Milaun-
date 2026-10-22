# Specification

## Problem

Nepali personal records are written in two scripts and an unbounded set of romanisations.
The same person may appear as `प्रवेश दाहाल`, `Prabesh Dahal`, `Pravesh Dahal` or
`Prabes Dahal`, and a surname may be `Dahal`, `दाहाल` or `दाहल`. Because clerks transcribe
phonetically, aspiration, retroflex/dental stops, vowel length and the final schwa all drift.

Identity workflows depend on joining such records:

- Nepal Rastra Bank requires banks to update customer KYC records with National ID data.
- The state links its citizenship and national-ID databases.
- Clinics, cooperatives, NGOs and municipalities deduplicate registers locally, offline.

Generic record-linkage libraries expose edit distance, Jaro-Winkler and Latin phonetic
codes; none provides a Devanagari-aware phonetic comparator, and Soundex-style codes are
defined for English orthography.

**Evidence status.** The policy facts above are cited in the README from public reporting.
The claim that these workflows *currently fail because of name matching* is a reasoned
inference, not a measured statistic: no public dataset of Nepali duplicate-rate errors was
found during development. Validating that inference with a partner organisation is the
first item on the roadmap.

## Users

| User | Task | Constraint |
|---|---|---|
| Clinic / hospital records officer | Reconcile a patient register | Offline, no data upload, low-end PC |
| Microfinance / cooperative accountant | Deduplicate member ledger | CSV in, reviewable output |
| NGO M&E officer | Merge beneficiary lists from two districts | No budget, no ML engineer |
| Municipal registry clerk | Find existing record before enrolling | Must not merge two citizens |
| Researcher | Link survey waves | Reproducible, citable method |

## Success metrics

Objective, measurable, and reported by `benchmarks/evaluate.py`:

1. **Precision at the auto-merge threshold** on held-out operations — target ≥ 0.98, because
   a false merge corrupts two identities.
2. **Recall at the same threshold** — reported, not maximised; the review band absorbs the rest.
3. **PR-AUC and ROC-AUC** on held-out operations, compared against tuned baselines.
4. **Expected calibration error** of the reported probability (target < 0.10).
5. **Blocking pair completeness** (target ≥ 0.98) and reduction ratio.
6. **Cluster-level pairwise precision/recall** and cluster purity.
7. **Latency and memory** on one CPU core (target < 5 ms/pair, < 100 MB).
8. **Reproducibility**: fixed seeds, deterministic outputs, one command.

## Non-goals

- Not a biometric or civil-registry system; names alone cannot separate homonyms.
- Not a general transliterator, and not evaluated on Hindi, Marathi or Bengali.
- Not a hosted service: no multi-tenancy, authentication or access control.
- Not a fuzzy-search engine for interactive autocomplete (blocking is batch-oriented).

## MVP scope (delivered)

- `compare`, `dedupe`, `link` over CSV and Python objects.
- Devanagari + Latin phonetic projection with consonant skeleton.
- Calibrated probability, three decision bands, cost-sensitive triage.
- Blocking index; audit store without a name column; HMAC pseudonymisation.
- CLI, local HTTP API and accessible review UI.
- Test suite, reproducible benchmark, CI, documentation.
