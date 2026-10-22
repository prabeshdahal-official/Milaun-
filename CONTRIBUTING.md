# Contributing

Thank you for considering a contribution. Milaun touches identity data, so the bar is
"correct, explainable, and honest about what is not known".

## Setup

```bash
git clone https://github.com/prabeshdahal-official/Milaun-.git
cd Milaun-
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[web,dev]"
pytest
ruff check .
```

## Before you open a pull request

1. `pytest` passes.
2. `ruff check .` is clean.
3. If you changed scoring, features, thresholds or the benchmark, run
   `python benchmarks/train.py && python benchmarks/evaluate.py` and paste the resulting
   table in the pull request. Do not hand-edit numbers.
4. New behaviour has a test. Bug fixes come with a regression test that fails before the fix.
5. Public functions have type hints and a docstring explaining *why*, not just *what*.

## What makes a good change

- **Evidence over assertion.** "This improves recall" needs the benchmark table, and a note
  on what it does to precision.
- **Rules over magic.** If a heuristic can be written as three readable rules, do that instead
  of adding a dependency.
- **Small diffs.** One concern per pull request; separate refactors from behaviour changes.
- **No new runtime dependencies in the core.** Web/UI dependencies belong in the `[web]` extra;
  anything else needs a strong justification.

## Areas where help is especially valuable

- **Real, consented, de-identified evaluation data** and an annotation protocol. This is worth
  more than any feature.
- Nepali linguistic review of the phonetic rules: regional spellings, caste and ethnic naming
  conventions, honorifics, clan names.
- Accessibility review of the web UI with a screen reader.
- Documentation in Nepali.

## Never include

- Real names, citizenship numbers, phone numbers, addresses, or records from a live system in
  tests, fixtures, issues, screenshots, or commit messages.
- Secrets, keys, audit databases (see `.gitignore`).
- Fabricated benchmarks, users, or citations. If a number cannot be reproduced, it does not go
  in the README.

## Style

- Python 3.10+, 100-column lines, `ruff` defaults from `pyproject.toml`.
- British spelling in prose, American spelling in identifiers where it is conventional.
- Comments explain rationale and trade-offs; the code explains itself.

## Commit messages

Imperative subject under ~72 characters, then a body explaining the problem and the decision.
Reference the issue when one exists. Example:

```
Fix negative-weight collapse in IRLS training

Collinear features let the optimiser drive one weight negative to compensate
for another. Training is now projected onto the non-negative orthant, which
keeps per-pair explanations consistent with the score.
```

## Review process

A maintainer reviews for correctness, tests, and honesty of claims. Expect questions about
failure modes. Disagreement is fine; unresolved disagreement is documented in the pull request.

By contributing you agree that your contribution is licensed under the MIT licence and that you
follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
