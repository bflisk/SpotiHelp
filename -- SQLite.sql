-- SQLite
CREATE TABLE users (id INTEGER NOT NULL, username TEXT NOT NULL, PRIMARY KEY(id));

INSERT INTO users (username) VALUES ('testuser2');

SELECT * FROM users;

DROP TABLE users;