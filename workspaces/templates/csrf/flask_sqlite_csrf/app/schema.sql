DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    balance INTEGER NOT NULL
);

INSERT INTO accounts (owner, balance) VALUES ('victim', 1000);

DROP TABLE IF EXISTS csrf_flags;
CREATE TABLE csrf_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL
);

INSERT INTO csrf_flags (token) VALUES ('FLAG-csrf-demo-token');

