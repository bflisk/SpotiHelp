-- SQLite
CREATE TABLE users (id INTEGER NOT NULL, username TEXT NOT NULL, PRIMARY KEY(id));
CREATE TABLE playlists (user_id INTEGER NOT NULL, playlist_id TEXT NOT NULL, playlist_name TEXT NOT NULL, playlist_link TEXT NOT NULL, is_smart TEXT NOT NULL, PRIMARY KEY(playlist_id), FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE playlist_options (user_id INTEGER NOT NULL, playlist_id TEXT NOT NULL, auto_add INTEGER NOT NULL, replace INTEGER NOT NULL, allow_explicit INTEGER NOT NULL, PRIMARY KEY(playlist_id), FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id));
CREATE TABLE playlist_tracks (user_id INTEGER NOT NULL, playlist_id TEXT NOT NULL, track_id TEXT NOT NULL, is_hearted INTEGER NOT NULL DEFAULT 0, num_skips INTEGER NOT NULL DEFAULT 0, row_id INTEGER NOT NULL, PRIMARY KEY(row_id), FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id));


CREATE TABLE user_data (user_id INTEGER NOT NULL, transaction_id INTEGER NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, data TEXT NOT NULL, num_sources INTEGER NOT NULL, sources TEXT NOT NULL, PRIMARY KEY (transaction_id));
INSERT INTO playlists (user_id, playlist_id, playlist_name) VALUES ('syluxhunter1352', "1AVZz0mBuGbCEoNRQdYQju", 'A Playlist');

SELECT * FROM users;

DELETE FROM playlists WHERE user_id=1;
DROP TABLE playlist_tracks;
DROP TABLE playlist_options;
DROP TABLE playlists;

END TRANSACTION;

CREATE INDEX playlists_options ON #FINISH THIS;

SELECT * FROM playlists WHERE playlist_id='25gN2E1Lbg6tUAvSyScmlt';