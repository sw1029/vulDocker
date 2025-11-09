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

DROP TABLE IF EXISTS audit_tokens;
CREATE TABLE audit_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL
);

INSERT INTO audit_tokens (token) VALUES ('FLAG-sqlite-demo-token');
