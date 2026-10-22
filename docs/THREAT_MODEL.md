# Threat model

## Assets

1. **Personal names and identifiers** processed by the user.
2. **The HMAC key** used for pseudonymisation.
3. **Audit databases** produced by `--store`.
4. **Integrity of merge decisions** — a wrong merge can deny someone a service or attach a
   debt to the wrong person.

## Adversaries and risks

| # | Threat | Mitigation | Residual risk |
|---|---|---|---|
| 1 | Data leaves the machine | Core and CLI make no network calls; UI binds to 127.0.0.1 | User runs `serve --host 0.0.0.0` |
| 2 | Names leak into logs or storage | No request-body logging; audit schema has no name column | Record ids may themselves be identifying |
| 3 | Shared dataset re-identifies people | `pseudonymize` uses keyed HMAC-SHA256 | Deterministic pseudonyms are dictionary-attackable over a small name space |
| 4 | Key theft | Key file created with owner-only permissions (POSIX) | Windows ACLs are inherited; protect the folder |
| 5 | CSV formula injection in exports | Cells starting with `= + - @ tab CR` are prefixed with `'` | Other spreadsheet quirks are out of scope |
| 6 | Malicious CSV causes resource exhaustion | 200k row cap, per-field length limits, streaming reader | A very wide file can still consume memory |
| 7 | Path traversal on output | Output path is taken verbatim from the user's own CLI flag | User can overwrite their own files |
| 8 | Wrong merge due to homonyms | Three-band triage; auto-merge requires ≥ 0.90; review pairs returned | Names alone cannot resolve homonyms |
| 9 | Adversarial name crafted to force a merge | Score is bounded by features; no user-supplied regex or code path | A crafted pair can still reach the review band |
| 10 | Model file tampering | JSON weights are validated against the feature list; unknown keys ignored | No signature on packaged artefacts |

## Privacy properties, stated plainly

- **Pseudonymisation is not anonymisation.** The same input maps to the same pseudonym by
  design (linkage requires it). With the key and a candidate list of names, an attacker can
  confirm membership. Use a high-entropy key, never commit it, and rotate per sharing context.
- **No differential privacy.** Aggregate statistics over small groups can leak.
- **No secure computation.** Two organisations sharing data must pseudonymise with the same key,
  which means one party holds it. A future protocol could use commutative hashing or PSI; today
  the honest advice is to link on a trusted machine.

## Operational guidance

1. Run on a machine you control; keep `*.db` and `*.key` out of version control (see `.gitignore`).
2. Pseudonymise identifiers before storing an audit trail if ids are personal data.
3. Treat the 0.55–0.90 band as mandatory human work, not as a queue to ignore.
4. Never auto-merge on names alone when the consequence of a false merge is denial of a
   benefit, a clinical decision, or a credit record. Add date of birth, address or an ID.
5. Do not expose the web UI beyond loopback without authentication and TLS.

## Out of scope

Multi-tenant access control, audit-log tamper-evidence (the SQLite file is append-only by
convention, not cryptographic), TLS termination, and denial-of-service hardening for
internet-facing deployment.
