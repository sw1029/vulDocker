CREATE TABLE IF NOT EXISTS accounts (
    id INT PRIMARY KEY,
    owner VARCHAR(64) NOT NULL,
    balance INT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_tokens (
    id INT PRIMARY KEY AUTO_INCREMENT,
    token VARCHAR(128) NOT NULL
);

INSERT INTO accounts (id, owner, balance) VALUES (1001, 'alice', 1200);
INSERT INTO accounts (id, owner, balance) VALUES (1002, 'bob', 800);
INSERT INTO audit_tokens (token) VALUES ('FLAG-super-secret-token');
