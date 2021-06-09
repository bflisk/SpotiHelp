# SPOTIHELP
# Brendan Flisk 2021
# ------------------
# Allows the user to have more advanced control 
# over their spotify library and experience
#


import os
import sys
import time
import math
import spotipy
import threading
import json
import spotipy.util as util

from pprint import pprint
from random import sample, randrange
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from os import environ
from functools import wraps
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth


# Configure application and API keys
app = Flask(__name__)
SPOTIPY_CLIENT_ID = environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = environ.get('SPOTIPY_CLIENT_SECRET')

# Creates secret key and names session cookie
app.secret_key = "GJOsgojhG08u9058hSDfj"
app.config["SESSION_COOKIE_NAME"] = "SpotiHelp Cookie"

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Initializes database and globals
db = SQL("sqlite:///spotihelp.db")
sp_oauth = None

# Globals
KEY = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] # Conversion values for keys
MODE = ['Major', 'Minor'] # Conversion values for mode
THREADS = {}


# Application
# --- Non-routable functions ---

# Requires user to log in before viewing certain pages
def login_required(f):
    # Wraps f, which is the function succeeding the login_required wrapper
    # Checks if the current session has a user id and routs the user to the login page if it doesn't exist
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrap


# Creates a spotify authorization object
def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=url_for('redirectPage',_external=True),
        scope="""ugc-image-upload user-read-recently-played user-read-playback-state 
        user-top-read app-remote-control playlist-modify-public user-modify-playback-state 
        playlist-modify-private user-follow-modify user-read-currently-playing user-follow-read 
        user-library-modify user-read-playback-position playlist-read-private user-read-email 
        user-read-private user-library-read playlist-read-collaborative streaming""")


# Returns a valid access token, refreshing it if needed
def get_token():
    token_info = session.get("token_info", None) # Gives token information if it exists, otherwise given 'None'

    # Checks if token_info is 'None' and redirects user to login
    if not token_info:
        return redirect(url_for("login", _external=True))

    # Checks if token is close to expiring
    now = int(time.time()) # Gets current time
    is_expired = (token_info['expires_at'] - now) < 60 # T or F depending on condition

    # If the token is close to expiring, refresh it
    if is_expired:
        sp_oauth = create_spotify_oauth() 
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
    
    session['token_info'] = token_info

    return token_info


# Clears user session and removes cache file
def clear_session():
    session.clear() # Gets rid of current session

    # Removes the cache file
    try:
        print("_____________________CACHE REMOVED_____________________")
        os.remove(r"C:\Users\Sylux\Desktop\Desktop\Code\WebDev\SpotiHelp\.cache")
    except:
        pass
        

# Creates a spotify object
def create_sp():
    # Tries to get token data. If it doesn't succeed, returns user back to index page
    try:
        token_info = get_token()
        sp = spotipy.Spotify(auth=token_info['access_token'])
    except:
        return redirect(url_for("login")) 

    return sp


# Checks Spotify for any changes in user's playlists, updates database, and returns a list
def get_playlists():
    sp = create_sp() # Creates a new spotify object

    batch = sp.current_user_playlists(limit=50, offset=0)['items']
    batchIterator = 0

    sp_playlists = [] # Spotify playlists
    db_playlists = [] # Database playlists
    playlists = [] # Updated playlist list

    # Gets playlist ID's from Spotify
    while batch:
        # Creates a list of user-managed playlists from Spotify
        for playlist in batch:
            if playlist['owner']['id'] == session['username']:
                sp_playlists.append(playlist['id'])

        # Iterates through batches until there are none left
        batchIterator += 1
        batch = sp.current_user_playlists(limit=50, offset=batchIterator*50)['items']
    
    # Gets playlist ID's from Database
    db_temp = db.execute("SELECT playlist_id FROM playlists WHERE user_id=?;", session['user_id'])
    for playlist in db_temp:
        db_playlists.append(playlist['playlist_id'])

    # Compares the two lists of playlists by ID's
    for playlist in db_playlists:
        if playlist in sp_playlists:
            playlists.append(playlist)
            sp_playlists.remove(playlist)
        else:
            db.execute("DELETE FROM playlists WHERE playlist_id=?;", playlist)
    
    # Adds playlists from Spotify that were not originally in the Database
    if len(sp_playlists) > 0:
        # Loops through playlist ID's
        for playlist in sp_playlists:
            playlist_info = sp.playlist(playlist) # Gets information about playlist from spotify
            db.execute("INSERT INTO playlists VALUES (?,?,?,?,?)", session['user_id'], playlist_info['id'], playlist_info['name'], playlist_info['external_urls']['spotify'], 0) # Inserts playlist into database

    playlists = db.execute("SELECT * FROM playlists WHERE user_id=?;", session['user_id']) # Gets updated list of playlists from database
    return playlists


# Gets the tracks off of a given playlist and returns them
def get_tracks(playlist_source):
    sp = create_sp() # Creates a new spotify object
    tracks = []
    batchIterator = 0

    if playlist_source == 'liked songs':
        # Gets all of the user's liked tracks
        batch = sp.current_user_saved_tracks(limit=50, offset=0)['items']

        while batch:
            for track in batch:
                tracks.append(track)

            batchIterator += 1
            batch = sp.current_user_saved_tracks(limit=50, offset=batchIterator*50)['items']

    else:
        batch = sp.playlist_tracks(playlist_source, limit=100, offset=0)['items']

        while batch:
            for track in batch:
                tracks.append(track)

            batchIterator += 1
            batch = sp.playlist_tracks(playlist_source, limit=100, offset=batchIterator*100)['items']

    return tracks


# Returns user's general preferences for a set of playlists
# TODO Get user's favorite artists and tracks
def get_user_data(source_url = False):
    if source_url != False:
        sp = create_sp() # Creates a new spotify object

        # An empty dict to store user's listening tendencies
        user_data = {
            "audio_features": {
                "mode": 0,
                "key": 0,
                "valence": 0,
                "speechiness": 0,
                "instrumentalness": 0,
                "loudness": 0,
                "energy": 0,
                "danceability": 0,
                "acousticness": 0,
                "liveness": 0,
                "tempo": 0
            },
            "favorite": {
                "artist": "",
                "track": "",
                "genre": ""
            }
        } 
        tracks = []

        # Parses playlist url and gets tracks off the playlist
        if len(source_url) != 22:
            playlist_id = source_url[34:56]
        else:
            playlist_id = source_url
        tracks.extend(get_tracks(playlist_id))

        # Packages the track ids
        batch = []
        for track in tracks:
            if track['track']['id'] != None:
                batch.append(track['track']['id'])

        # Analyzes audio features of tracks
        # TODO Add batches
        playlist_size = 0
        total_track_features = sp.audio_features(tracks=batch)

        for features in total_track_features:
            for feature in features:
                try:
                    user_data['audio_features'][feature] += features[feature] # Adds up all values for each feature
                except:
                    pass
            playlist_size += 1
        
        # Calculates the average value for each feature
        for feature in user_data['audio_features']:
            user_data['audio_features'][feature] /= playlist_size
            if feature == 'tempo' or feature == 'key' or feature == 'loudness':
                user_data['audio_features'][feature] = round(user_data['audio_features'][feature], 0)
            else:
                user_data['audio_features'][feature] = round(user_data['audio_features'][feature], 3)

        return user_data
    return source_url


# Gets additional songs from Spotify
def seed_more_tracks(limit, artists, genres, total_tracks):
    sp = create_sp()
    playlist_options = session['playlist_options']
    results = []
    tracks = [] # Clears the seeds  

    # Randomly chooses tracks to seed (Makes sure there are 5 total seed sources)
    if len(total_tracks) >= (5 - len(genres)):
        for i in range(5 - (len(genres + artists))):
            tracks.extend(sample(total_tracks, 1))

    # Sets value to None if the list is empty
    if artists == [] or artists == ['']:
        artists = None
    elif genres == [] or genres == ['']:
        genres = None
    elif tracks == set():
        tracks = None 
    
    # Chooses a random key to seed
    if playlist_options['key'] == [] or playlist_options['key'] == ['']:
        key = None
    else:
        key = playlist_options['key'][randrange(len(playlist_options['key']))]

    # Makes sure app makes a valid request to Spotify
    if artists == None and genres == None and tracks == None:
        print('error')
        return error("No seeds")

    # Fetches tracks from Spotify's recommendation system that match user parameters
    batch = sp.recommendations(seed_artists=None, seed_genres=None, seed_tracks=[playlist_options['seed_track']], limit=limit, country=None, 
        target_key=key, 
        min_mode=mode[0], max_mode=mode[1])['tracks'] 
    """target_valence=playlist_options['valence'], min_valence=get_bound('valence', changes['valence'])['min'], max_valence=get_bound('valence', changes['valence'])['max'], 
    target_speechiness=playlist_options['speechiness'], min_speechiness=get_bound('speechiness', changes['speechiness'])['min'], max_speechiness=get_bound('speechiness', changes['speechiness'])['max'], 
    target_instrumentalness=playlist_options['instrumentalness'], min_instrumentalness=get_bound('instrumentalness', changes['instrumentalness'])['min'], max_instrumentalness=get_bound('instrumentalness', changes['instrumentalness'])['max'], 
    target_loudness=playlist_options['loudness'], min_loudness=get_bound('loudness', changes['loudness'])['min'], max_loudness=get_bound('loudness', changes['loudness'])['max'], 
    target_energy=playlist_options['energy'], min_energy=get_bound('energy', changes['energy'])['min'], max_energy=get_bound('energy', changes['energy'])['max'], 
    target_danceability=playlist_options['danceability'], min_danceability=get_bound('danceability', changes['danceability'])['min'], max_danceability=get_bound('danceability', changes['danceability'])['max'], 
    target_acousticness=playlist_options['acousticness'], min_acousticness=get_bound('acousticness', changes['acousticness'])['min'], max_acousticness=get_bound('acousticness', changes['acousticness'])['max'], 
    target_liveness=playlist_options['liveness'], min_liveness=get_bound('liveness', changes['liveness'])['min'], max_liveness=get_bound('liveness', changes['liveness'])['max'], 
    target_tempo=playlist_options['tempo'], min_tempo=get_bound('tempo', changes['tempo'])['min'], max_tempo=get_bound('tempo', changes['tempo'])['max'])['tracks']"""

    for track in batch:
        results.append(track['id'])
    
    return results


# TODO Stores options for smart playlist in database
def store_options(playlist_id):
    playlist_options = session['playlist_options']

    db.execute("INSERT INTO playlist_options VALUES (?,?,?,?,?)", session['user_id'], playlist_id, playlist_options)

    return


# Tracks user playback and logs track skips
def log_playback(user_id):
    sp = create_sp()
    past_track_id = None

    while True:
        # TODO change current_playback()
        current_track_id = sp.current_playback()
        track_position = sp.current_playback()

        if current_track_id != past_track_id:
            if track_position < track_duration / 2:
                db.execute("UPDATE") # TODO Add a skip to the track

            track_duration = sp.current_playback()

        past_track_id = current_track_id

        time.sleep(2)

    return


# Stores tracks into the database to prevent copies
def store_tracks(playlist_id, track_list):
    for track in track_list:
        db.execute("INSERT INTO playlist_tracks (user_id, playlist_id, track_id) VALUES (?,?,?)", session['user_id'], playlist_id, track)

    return


# Seeds a new track from a given track
def seed_new_track(seed):
    sp = create_sp()

    track = sp.recommendations(
            seed_artists=None, seed_genres=None, seed_tracks=[seed], limit=1)['tracks']
    track_id = track[0]['id']

    return track_id


# Manages a user's playlist as a separate thread
# TODO Exit the thread and close logger thread if the user deletes the playlist or turns off the smart playlist feature
def manage_playlist(user_id, playlist_id, playlist_options, playlist_tracks, seed, session):
    # TODO Starts a thread that logs user skips if the user selected the 'replace' option
    """if playlist_options['replace']:
        logger_thread = threading.Thread(
            target=log_playback, args=[session['user_id']])
        logger_thread.start()
        THREADS[f"{session['username']}_{playlist_id}"].append(logger_thread)"""

    # Loops with a user-set frequency and adds/replaces tracks according to that frequency
    while True:
        sp = create_sp()

        # Waits the designated time interval specified
        time.sleep(playlist_options['auto_add'][2])

        # Seeds a new track to add to the playlist
        track_id = seed_new_track(seed)

        # Removes a track from the given playlist if the user set the option
        # TODO check for user-set max skips
        """if playlist_options['replace']:
            candidates = db.execute(
                "SELECT track_id, num_skips FROM playlist_tracks WHERE user_id=? AND is_hearted=? AND playlist_id=?", user_id, 0, playlist_id)"""
            
            # TODO Check database for most-skipped tracks and non-favorited tracks

        # Checks to make sure that track has not been added before and seeds another one if it has been added
        fail_count = 0
        while fail_count < 50:
            if track_id not in playlist_tracks:
                sp.user_playlist_add_tracks(
                    session['username'], playlist_id, [track_id], position=None)

                playlist_tracks.add(track_id)
                db.execute("INSERT INTO playlist_tracks (user_id, playlist_id, track_id) VALUES (?,?,?)",
                        user_id, playlist_id, track_id)
                break
            else:
                track_id = seed_new_track(seed)
                fail_count += 1


    return

# --- Routable functions ---

# Has the user log in and authorize SpotiHelp to use information from Spotify
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        clear_session()

        sp_oauth = create_spotify_oauth() # Creates a new sp_oauth object everytime a user logs in
        auth_url = sp_oauth.get_authorize_url() # Passes the authorization url into a variable

        return redirect(auth_url) # Redirects user to the authorization url
    else:
        return render_template("login.html")


# Homepage
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("search")

        spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())

        results = spotify.search(q='artist:' + name, type='artist')
        items = results['artists']['items']
        if len(items) > 0:
            artist = items[0]
            print(artist['name'], artist['images'][0]['url'])

        return render_template("index.html", results=results['artists']['items'])

    else:
        return render_template("index.html")


# Redirects user after logging in and adds them to the user database
@app.route("/redirect")
def redirectPage():
    sp_oauth = create_spotify_oauth() # Creates a new sp_oauth object
    session.clear()
    
    code = request.args.get('code') # Gets code from response URL
    token_info = sp_oauth.get_access_token(code) # Uses code sent from Spotify to exchange for an access & refresh token
    session["token_info"] = token_info # Saves token info into the the session
    sp = create_sp()
    session["username"] = sp.current_user()['display_name'] # Sets session username
    #session["user_id"] = generate_password_hash(session["username"],method='pbkdf2:sha256', salt_length=8) # Generate unique id for user

    # Checks if the user is registered and adds to database accordingly
    if not db.execute("SELECT * FROM users WHERE username=?", session["username"]):
        db.execute('INSERT INTO users (username) VALUES (?);', session["username"])

    session["user_id"] = db.execute("SELECT id FROM users WHERE username=?", session["username"])[0]['id'] # Sets session user id
        
    return redirect(url_for("index", _external=True))


# TODO Error Page (Check how CS50 does it)
@app.route("/error")
def error(msg):
    return render_template("error.html", msg=msg)


# Logs user out
@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    clear_session()
    return redirect(url_for("index"))


# Allows the user to create new smart playlists
@app.route("/playlist-new", methods=["GET", "POST"])
@login_required
def new_playlist():
    sp = create_sp() # Creates a new spotify object 

    # Clears previous options
    playlist_options = {}
    session['playlist_options'] = None

    if request.method == "POST":
        # Gets user's desired new playlist parameters
        playlist_options.update({"name": request.form.get("playlist_name")})
        playlist_options.update({"public": request.form.get("playlist_pub")})
        playlist_options.update({"description": request.form.get("playlist_desc")})
        playlist_options.update({"seed_track": str(request.form.get("playlist_seed_track"))}) # Gets a list of track ids that will be used to seed a new playlist
        playlist_options.update({"size": int(request.form.get("size"))}) # Number of songs in playlist

        # Auto playlist management settings
        playlist_options.update({"auto_add": [request.form.get("playlist_auto_add"), request.form.get("playlist_auto_add_replace"), int(request.form.get("playlist_update_freq"))]})
        playlist_options.update({"auto_delete": [request.form.get("playlist_auto_delete"), request.form.get("playlist_auto_delete_skips_req")]})
        playlist_options.update({"allow_explicit": request.form.get("playlist_allow_explicit")})

        # Parses information
        if playlist_options['auto_add'][0] == None:
            playlist_options['auto_add'][0] = False
        else:
            playlist_options['auto_add'][0] = True
        if playlist_options['auto_add'][1] == None:
            playlist_options['auto_add'][1] = False
        if playlist_options['auto_delete'][0] == None:
            playlist_options['auto_delete'][0] = False
        
        if playlist_options['auto_add'] or playlist_options['auto_delete']:
            playlist_options.update({'is_smart': True})
        else:
            playlist_options.update({'is_smart': False})
        
        # Parses whether playlis is public or not
        if playlist_options['public'] == 'on':
            playlist_options['public'] = True
        else:
            playlist_options['public'] = False

        session['playlist_options'] = playlist_options

        return redirect(url_for("new_playlist_create"))
    else:
        return render_template("playlist-new.html")


# Prompts for final options and creates the user-generated smart playlist
@app.route("/playlist-new/create", methods=["GET", "POST"])
@login_required
def new_playlist_create():
    sp = create_sp() # Creates a new spotify object
    playlist_options = session['playlist_options']

    # If the user confirms their options
    if request.method == "POST":
        total_tracks = set() # A set of unique tracks to be added to the new playlist
        fail_count = 0
        recs_list = []
        past_recs = None

        # Populates playlist with unique tracks
        while len(total_tracks) < playlist_options['size'] and fail_count < 6:
            # Gets a batch of seeded tracks from Spotify
            recs_dict = sp.recommendations(seed_artists=None, seed_genres=None, seed_tracks=[playlist_options['seed_track']],
                                                limit=(playlist_options['size'] - len(total_tracks) if playlist_options['size'] - len(total_tracks) < 50 else 50), country=None)['tracks']
            
            # Converts the needed values from the dictonary into a list
            for rec in recs_dict:
                recs_list.append(rec['id'])
            recs_list.sort()

            # Makes sure there is no infinite loop 
            if past_recs == recs_list:
                fail_count += 1
            past_recs = recs_list
            past_recs.sort()

            # Adds batch tracks into the total set
            total_tracks |= set(recs_list)
            
        # Creates a new empty playlist with user parameters
        new_playlist = sp.user_playlist_create(session['username'], playlist_options['name'], public=session['playlist_options']['public'], description=session['playlist_options']['description'])

        # Adds tracks to playlist
        batch = []
        total_tracks_list = list(total_tracks) # Converts the set into a list

        for batchIterator in range(len(total_tracks_list)):
            batch.append(total_tracks_list[batchIterator])
            batchIterator += 1 

            # Adds tracks in batches of 100
            if batchIterator % 100 == 0:
                sp.user_playlist_add_tracks(session['username'], new_playlist['id'], batch, position=None)
                batch = []

        # Adds remaining tracks (< 100)
        if len(batch) > 0:
            sp.user_playlist_add_tracks(session['username'], new_playlist['id'], batch, position=None)

        # Stores the playlist info into database
        db.execute("INSERT INTO playlists VALUES (?,?,?,?,?);", session['user_id'], new_playlist['id'], new_playlist['name'], new_playlist['href'], str(playlist_options['is_smart']))
        if playlist_options['is_smart']:
            db.execute("INSERT INTO playlist_options (user_id, playlist_id, auto_add, replace, allow_explicit) VALUES (?,?,?,?,?);", session['user_id'], new_playlist['id'], str(playlist_options['auto_add']), str(playlist_options['auto_add'][1]), str(playlist_options['auto_add'][2]))
        store_tracks(new_playlist['id'], total_tracks_list)

        # If requested, starts a new threaded process that manages the new playlist
        if playlist_options['is_smart']:
            manager_thread = threading.Thread(target=manage_playlist, args=[session['user_id'], new_playlist['id'], playlist_options, total_tracks, playlist_options['seed_track'], session])
            manager_thread.start()
            THREADS.update({f"{session['username']}_{new_playlist['id']}": [manager_thread]})
        
        return render_template("playlist-new-create.html", playlist_options=playlist_options, created=True)
    else:
        return render_template("playlist-new-create.html", playlist_options=playlist_options, created=False)


# Allows the user to edit existing playlists
@app.route("/playlist-edit")
@login_required
def edit_playlist():
    # Gets the user's playlists
    sp = create_sp()
        
    playlists = get_playlists() # Gets updates list of user's current playlists

    return render_template("playlist-edit.html", playlists=playlists)


# Opens up a specific playlist for a user to edit
@app.route("/playlist-edit/<playlist>")
@login_required
def edit_specific_playlist(playlist):
    # Gets playlist information
    sp = create_sp()
    playlist_id = playlist
    playlist_info = sp.playlist(playlist_id)

    # Tries to get playlist art
    try:
        playlist_art = playlist_info['images'][0]['url']
    except:
        playlist_art = ''

    # Parses playlist information into a list
    playlist = {'playlist_id': playlist_id, 'playlist_name': playlist_info['name'], 
                'playlist_art': playlist_art, 'playlist_link': playlist_info['external_urls']['spotify'], 
                'tracks': []}
    
    # Gets tracks on the playlist
    for track in playlist_info['tracks']['items']:
        playlist['tracks'].append(track)

    return render_template("playlist-edit-specific.html", playlist=playlist)


# Displays the user's listening habits
# TODO If user's source playlists have changed, update listening habits
# TODO Keep track of changes in listening habits
@app.route("/data", methods=["GET", "POST"])
@login_required
def show_user_data():
    sp = create_sp()

    # If the user wants to add another source for their listening habits
    # TODO Add funcionality to add multiple playlists at one time
    if request.method == "POST":
        sources = [] # Sources currently being added
        db_sources = [] # Sources that were already in the database
        sources.append(request.form.get("playlist_ids")) # A list of playlists user wants to add as sources

        # Gets total playlists currently being used as sources
        try:
            total_playlists = len(sources) + db.execute("SELECT total_sources FROM user_data WHERE user_id=?;", session['user_id'])[0]['total_sources'] # Number of playlists
        except:
            total_playlists = len(sources)
        
        # Gets a list of the current sources used
        try:
            db_sources = json.loads(db.execute("SELECT sources FROM user_data WHERE user_id=?;", session['user_id'])[0]['sources'])
        except:
            pass
        
        """# Makes sure the user can't enter a source that's already being used
        for source in sources:
            if source in db_sources:
                sources.remove(source)
                print(f"{source} was not added!")"""

        # Appends database sources if the list is not empty
        if db_sources != []:
            sources.extend(db_sources)

        # An empty dict to store user's listening tendencies
        user_data = {
            "audio_features": {
                "mode": 0,
                "key": 0,
                "valence": 0,
                "speechiness": 0,
                "instrumentalness": 0,
                "loudness": 0,
                "energy": 0,
                "danceability": 0,
                "acousticness": 0,
                "liveness": 0,
                "tempo": 0
            },
            "favorite": {
                "artist": "",
                "track": "",
                "genre": ""
            }
        } 

        # Loops through user's playlist sources and merges values
        for playlist_id in sources:
            new_data = get_user_data(playlist_id)['audio_features']
            for feature in user_data['audio_features']:
                user_data['audio_features'][feature] += new_data[feature]
        
        # Gets averages for each feature
        for feature in user_data['audio_features']:
            user_data['audio_features'][feature] /= total_playlists

        # Updates and pulls from database
        db.execute("INSERT INTO user_data (user_id, data, num_sources, sources) VALUES (?,?,?,?);", session['user_id'], json.dumps(user_data), total_playlists, json.dumps(sources)) # Updates user data
        user_data = db.execute("SELECT * FROM user_data WHERE user_id=?;", session['user_id']) # Gets updated user data

        return redirect(url_for("show_user_data"))
    else:
        current_user_playing_track = sp.current_user_playing_track()
        current_playback = sp.current_playback()
        currently_playing = sp.currently_playing()

        print("====================================================================================================")
        pprint(current_user_playing_track)
        print("----------------------------------------------------------------------------------------------------")
        pprint(current_playback)
        print("----------------------------------------------------------------------------------------------------")
        pprint(currently_playing)
        print("====================================================================================================")

        """user_data = []
        playlists = get_playlists() # Gets updates list of user's current playlists
        try:
            user_data = db.execute("SELECT * FROM user_data WHERE user_id=?;", session['user_id'])[0] # Gets user data
        except:
            user_data = ["Nothing Yet ;)"]
        history = db.execute("SELECT * FROM user_data WHERE user_id=?;", session['user_id'])"""

        """for data in user_data:
            user_data.append(json.loads(data['sources']))
            user_data.append(json.loads(data['data']))"""

        return render_template("show-user-data.html", current_user_playing_track=current_user_playing_track, current_playback=current_playback, currently_playing=currently_playing)