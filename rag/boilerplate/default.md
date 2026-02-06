# Executor Constraints (Read-only Container)

The bundle will be executed inside Docker with:

- `--read-only`
- a tmpfs mount at `/tmp` (writable)
- reduced privileges (`--cap-drop ALL`, `no-new-privileges`)

Guidelines:

- Store **all runtime state** under `/tmp` (DB files, uploads, caches, etc.).
- Do **not** write to the working directory (commonly `/app`) at runtime.
- Avoid relying on **runtime OS binaries** (e.g., `sqlite3`, `psql`, `mysql`, `curl`, `wget`).
  - Prefer language-native libraries.
  - If an OS binary is truly required, install it in the Dockerfile and keep it.
- Services must bind `0.0.0.0` and listen on the declared port (default 5000).

