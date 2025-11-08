import os
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, request

APP_DB_PATH = os.environ.get("APP_DB_PATH", "/tmp/app.db")
PORT = int(os.environ.get("APP_PORT", "5000"))

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
    Path(APP_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
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
    query = f"SELECT id, username, password FROM users WHERE id = {user_id};"
    app.logger.warning("Executing raw query: %s", query)
    db = get_db()
    rows = db.execute(query).fetchall()
    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
