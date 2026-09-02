# Log-site index

## Record

A site is one logging call in one commit:

- `fingerprint`: format string with `%d`/`%s`, numbers, hex, and paths replaced by `%`
- `basename` + `path` + `line`
- `macro` / Python logger name and `level` (including EVENT)
- `error_codes` pulled from the format string
- `source_line` (single line, enough for agents without the tree)

## Incremental rule

Re-index a clone when `git rev-parse HEAD` differs from the last snapshot for that `repo_id`. Query never fetches. If the clone is missing, `index` errors with the catalog URL; `locate` still returns `embedded` file:line from the log itself.

## Matching order

1. Embedded `[file:line]` from the log (always returned)
2. Same basename + fingerprint (high)
3. Same basename, nearby or drifted line (medium)
4. Fingerprint in candidate repos from slog `ModuleName` (low)

## Staleness

If basename matches and fingerprint matches but line differs, the hit is valid and flagged `line_drift`. Prefer this over HEAD of the wrong version.
