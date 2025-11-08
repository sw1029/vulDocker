# MVP SQLi Context Snapshot

- CWE-89(SQL Injection) reference with focus on string concatenation vulnerabilities.
- Target stack: Python 3.11 + Flask + SQLite for deterministic reproduction.
- PoC expectation: send crafted `id` parameter ("1 OR 1=1") to dump entire users table.
- Execution environment: run inside Docker with network disabled, rely on sqlite file.
