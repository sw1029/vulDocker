# Flask + SQLite Boilerplate (No CLI, /tmp DB)

Use Python's `sqlite3` module (no `sqlite3` CLI) and keep the DB under `/tmp`.

Recommended pattern (service-side):

```python
import os
import sqlite3
from pathlib import Path

APP_DB_PATH = os.environ.get("APP_DB_PATH", "/tmp/app.db")

def init_sqlite_db(db_path: str, schema_path: str, seed_path: str | None = None) -> None:
    p = Path(db_path)
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = Path(schema_path).read_text(encoding="utf-8")
    seed_sql = Path(seed_path).read_text(encoding="utf-8") if seed_path else ""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        if seed_sql.strip():
            conn.executescript(seed_sql)
        conn.commit()
    finally:
        conn.close()
```

If the app performs INSERT/UPDATE/DELETE, ensure `APP_DB_PATH` is under `/tmp`.

