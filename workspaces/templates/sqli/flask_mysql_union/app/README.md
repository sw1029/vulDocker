# Flask + MySQL UNION SQLi

- `/statement` concatenates the `account` parameter directly into an SQL statement and chains a UNION against `audit_tokens` to leak secrets.
- Runtime expects a companion MySQL container reachable at `sqli-db:3306`.
- PoC executes `python poc.py --base-url http://127.0.0.1:5000 --payload "1001 OR 1=1"`.

## Files
- `app.py` – Flask app with bootstrap + unsafe endpoint.
- `schema.sql` – Reference schema mirrored from `SCHEMA_STATEMENTS`.
- `Dockerfile` – installs Flask + mysql-connector.
- `requirements.txt` – dependency pin set.
- `poc.py` – waits for the service then performs UNION-based SQLi.
