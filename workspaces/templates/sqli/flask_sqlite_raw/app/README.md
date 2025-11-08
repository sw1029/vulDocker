# Flask + SQLite raw SQL (CWE-89)

- Endpoint `/profile` concatenates untrusted `id` parameter directly into the query.
- Database: local SQLite file stored at `/tmp/app.db`.
- PoC: `python poc.py --base-url http://127.0.0.1:5000 --payload "1 OR 1=1"`.

## Files
- `app.py` – Flask service exposing `/users` and `/profile`.
- `schema.sql` – bootstrap script executed on first start.
- `Dockerfile` – deterministic runtime pinned to python:3.11-slim.
- `requirements.txt` – locked dependencies.
- `poc.py` – HTTP exploit script that prints the leaked rows.
