"""Vulnerable Flask-like login workflow using raw SQL strings."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'data.db'


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)')
    cur.execute('DELETE FROM users')
    cur.execute('INSERT INTO users(username, password) VALUES ("admin", "secret"), ("guest", "guest")')
    conn.commit()
    conn.close()


def vulnerable_login(username: str, password: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = f"SELECT username FROM users WHERE username = '{username}' AND password = '{password}'"
    cur.execute(query)
    row = cur.fetchone()
    conn.close()
    return row is not None


def dump_users() -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT username, password FROM users')
    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == '__main__':
    init_db()
    print('Users:', dump_users())
