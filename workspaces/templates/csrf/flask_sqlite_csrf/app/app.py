import os
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, request

APP_DB_PATH = os.environ.get("APP_DB_PATH", "/tmp/csrf_app.db")
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


@app.route("/balance", methods=["GET"])
def balance():
    db = get_db()
    row = db.execute("SELECT owner, balance FROM accounts LIMIT 1").fetchone()
    return jsonify({"owner": row["owner"], "balance": row["balance"]})


@app.route("/transfer", methods=["POST"])
def transfer():
    payload = request.form or request.json or {}
    amount = 0
    try:
        amount = int(payload.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    amount = max(amount, 0)

    db = get_db()
    db.execute("UPDATE accounts SET balance = balance - ?", (amount,))
    db.commit()

    flag_row = db.execute("SELECT token FROM csrf_flags LIMIT 1").fetchone()
    balance_row = db.execute("SELECT balance FROM accounts LIMIT 1").fetchone()
    flag_value = flag_row["token"] if flag_row else "UNKNOWN"
    app.logger.warning("State change performed without CSRF token. amount=%s", amount)
    return jsonify(
        {
            "status": "transfer-complete",
            "balance": balance_row["balance"],
            "flag": flag_value,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

