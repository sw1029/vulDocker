# Python Bundle Notes

- Do not add standard-library modules (e.g., `logging`, `sqlite3`) to `deps[]`.
- Prefer small, deterministic startup code that works in a `--read-only` container.
- If you need runtime files, write them under `/tmp`.

