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
