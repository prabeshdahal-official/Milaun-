# Security policy

## Supported versions

Milaun is at `0.1.x`. Security fixes are applied to the latest release only.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

- Open a private security advisory on GitHub
  (`Security` → `Advisories` → `Report a vulnerability`), or
- email the maintainer listed in `CITATION.cff`.

Include: affected version, a minimal reproduction, and the impact you believe it
has. You can expect an acknowledgement within 7 days.

## Scope

Milaun is a local library and CLI. The relevant threat surface is:

1. **Sensitive input handling.** Names are personal data. The package must never
   transmit, log, or persist raw names outside the paths the user chooses.
2. **Path and CSV handling.** Crafted CSV files must not cause code execution,
   spreadsheet formula injection, or writes outside the specified output path.
3. **The optional local HTTP server.** It binds to `127.0.0.1` by default; request
   bodies are size-limited by field and record caps.
4. **Dependency surface.** The core has no third-party runtime dependencies; the
   `[web]` extra pulls FastAPI and Uvicorn and should be updated with them.

## Known non-goals

- Milaun does not authenticate users or enforce access control. Run it on a machine
  you control and protect the filesystem yourself.
- Pseudonymisation is keyed HMAC-SHA256, which is deterministic and therefore
  vulnerable to dictionary attacks over a small name space. It is designed for
  linkage, not for irreversible anonymisation. See `docs/THREAT_MODEL.md`.
- The web UI is a local review aid, not an internet-facing service. Do not expose
  it publicly without adding authentication, TLS and rate limiting.

## Handling of audit data

`--store` writes record identifiers, probabilities and feature vectors to SQLite.
The schema deliberately has no name column. If your identifiers are themselves
personal data, pseudonymise them first (`milaun pseudonymize`).
