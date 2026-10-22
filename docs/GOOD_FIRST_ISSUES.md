# Good first issues

Each item is scoped to be finishable in an evening, has a clear acceptance criterion, and
does not require access to private data. Copy these into GitHub issues as-is.

## 1. Add a `milaun explain --json` golden-file test

**Why:** the explanation strings are user-facing and untested.
**Do:** capture `compare(..., ).as_dict()["reasons"]` for five representative pairs into a
fixture; assert the reasons still match.
**Done when:** a change to `Matcher.explain` that removes a reason fails a test.

## 2. Support `--auto`/`--review` in the web UI

**Why:** thresholds are configurable in the CLI but fixed in the UI.
**Do:** add two number inputs, send them with the compare/dedupe request, validate ordering.
**Done when:** the UI refuses `review > auto` with an accessible error message.

## 3. Add a Nepali (`ne`) translation of the UI strings

**Why:** most users of the tool read Nepali more comfortably than English.
**Do:** extract strings into a small JS dictionary, add a language toggle, keep `lang="ne"`.
**Done when:** every visible string switches and the page still passes keyboard navigation.

## 4. Report per-token alignments in the explanation

**Why:** "which token matched which" is the first question a reviewer asks.
**Do:** return the best-match pairing from `token_min_sim` and render it in the UI.
**Done when:** `compare("Ram Bahadur Thapa", "Ram B. Thapa")` shows the dropped middle token.

## 5. Benchmark `--limit` and progress output

**Why:** the demo on 100k rows gives no feedback.
**Do:** add `--progress` printing every 5,000 records to stderr, and `--limit N`.
**Done when:** piping stdout to a file keeps JSON clean and progress goes to stderr.

## 6. Property-based tests with Hypothesis

**Why:** Unicode edge cases (nukta, chandrabindu, ZWJ, mixed script) are easy to miss.
**Do:** add a `dev` extra with Hypothesis; assert normalisation is idempotent and keys never
raise for arbitrary Unicode strings.
**Done when:** 1,000 generated examples pass and shrink failures are readable.

## 7. Fix the middle-initial weak case

**Why:** `राम बहादुर थापा` vs `Ram B. Thapa` scores far too low; a dropped middle name is
common and should not read as "distinct".
**Do:** investigate the key/length interaction, consider a containment feature, retrain.
**Done when:** the pair lands in the review band or above without hurting hard-test precision.

## 8. Export a review queue as CSV with a stable order

**Why:** reviewers need a deterministic worklist.
**Do:** add `milaun review-queue` that writes `left_id,right_id,probability,reasons`.
**Done when:** two runs on the same input produce byte-identical files.

## 9. Document and test the `link` command with different column names

**Why:** `--left-col`/`--right-col` currently has an awkward code path in `cli.py`.
**Do:** simplify it and add an integration test with two differently-named CSVs.
**Done when:** the branch that rebuilds records is gone and the test covers it.
