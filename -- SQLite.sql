-- SQLite
CREATE TABLE users (id INTEGER NOT NULL, username TEXT NOT NULL, PRIMARY KEY(id));
CREATE TABLE playlists (user_id INTEGER NOT NULL, playlist_id TEXT NOT NULL, playlist_name TEXT NOT NULL, playlist_art TEXT NOT NULL, playlist_link TEXT NOT NULL, PRIMARY KEY(playlist_id));

INSERT INTO playlists (user_id, playlist_id, playlist_name) VALUES ('syluxhunter1352', "1AVZz0mBuGbCEoNRQdYQju", 'A Playlist');

SELECT * FROM users;

DELETE FROM playlists WHERE user_id=1;
DROP TABLE playlists;