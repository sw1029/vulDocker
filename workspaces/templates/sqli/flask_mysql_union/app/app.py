import os
import time
from contextlib import closing

import mysql.connector
from flask import Flask, jsonify, request

APP_PORT = int(os.environ.get("APP_PORT", "5000"))

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "sqli-db"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "sqli"),
    "password": os.environ.get("DB_PASSWORD", "sqli_pw"),
    "database": os.environ.get("DB_NAME", "sqliapp"),
}

SCHEMA_STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS accounts (id INT PRIMARY KEY, owner VARCHAR(64), balance INT)",
    "CREATE TABLE IF NOT EXISTS audit_tokens (id INT PRIMARY KEY AUTO_INCREMENT, token VARCHAR(128) NOT NULL)",
    "INSERT INTO accounts (id, owner, balance) VALUES (1001, 'alice', 1200) ON DUPLICATE KEY UPDATE owner=VALUES(owner), balance=VALUES(balance)",
    "INSERT INTO accounts (id, owner, balance) VALUES (1002, 'bob', 800) ON DUPLICATE KEY UPDATE owner=VALUES(owner), balance=VALUES(balance)",
    "INSERT INTO audit_tokens (token) VALUES ('FLAG-super-secret-token') ON DUPLICATE KEY UPDATE token=token",
]

app = Flask(__name__)


def _connect(database: str | None = None):
    cfg = DB_CONFIG.copy()
    if database:
        cfg["database"] = database
    return mysql.connector.connect(**cfg)


def wait_for_db():
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with closing(_connect(database=None)) as conn:
                cursor = conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
                conn.commit()
            return
        except mysql.connector.Error:
            time.sleep(2)
    raise RuntimeError("Database not reachable within timeout")


def bootstrap_schema():
    wait_for_db()
    with closing(_connect()) as conn:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        conn.commit()


bootstrap_schema()


def query_db(sql: str):
    with closing(_connect()) as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        return cursor.fetchall()


@app.route("/accounts")
def accounts():
    rows = query_db("SELECT id, owner, balance FROM accounts ORDER BY id")
    return jsonify(rows)


@app.route("/statement")
def unsafe_statement():
    account = request.args.get("account", "1001")
    # CWE-89: account parameter is concatenated, allowing UNION-based injection.
    sql = (
        "SELECT id, owner, balance FROM accounts WHERE id = "
        f"{account} UNION SELECT id, token as owner, token as balance FROM audit_tokens"
    )
    app.logger.warning("Executing raw SQL: %s", sql)
    rows = query_db(sql)
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
