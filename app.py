# SPOTIHELP
# Brendan Flisk 2021
# ------------------
# Allows the user to have more advanced control 
# over their spotify library and experience
#


import os
import sys
import time
import spotipy
import spotipy.util as util

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
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


# Checks Spotify for any changes in user's playlists and returns an updated list
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
            print("++++++++++++++++++++++++++++++++++")
            print(playlist_info)
            db.execute("INSERT INTO playlists VALUES (?,?,?,?,?)", session['user_id'], playlist_info['id'], playlist_info['name'], playlist_info['external_urls']['spotify'], 0) # Inserts playlist into database

    playlists = db.execute("SELECT * FROM playlists WHERE user_id=?;", session['user_id']) # Gets updated list of playlists from database
    return playlists


# TODO Gets playlist art
def get_artwork():
    sp = create_sp()

    # Gets playlist ID's from Database
    db_temp = db.execute("SELECT playlist_id FROM playlists WHERE user_id=?;", session['user_id'])
    for playlist in db_temp:
        db_playlists.append(playlist['playlist_id'])
    
    return playlist_art

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


# Logs user out
@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    clear_session()
    return redirect(url_for("index"))


# Gets user saved tracks
@app.route("/get-tracks", methods=["GET", "POST"])
@login_required
def getTracks():
    sp = create_sp() # Creates a new spotify object 
    total_tracks = sp.current_user_saved_tracks(limit=1, offset=0)['total'] # Total tracks user has saved
    result_size = 20 # Amounts of tracks to show per page

    if request.method == "POST": 
        pageNum = session["track_pageNum"] # Gets the current page number
        pageNum += int(request.form.get("page")) # Moves one page forward or backward

        # If the user specifies a page number, take them there
        if request.form.get("pageSearch"):
            pageNum = int(request.form.get("pageSearch"))

        # Makes sure page number is valid
        if pageNum < 0:
            pageNum = 0
        elif pageNum > total_tracks/result_size:
            pageNum = int(total_tracks/result_size) 
        
        session["track_pageNum"] = pageNum # Sets the session's page number       
        saved_tracks = sp.current_user_saved_tracks(limit=result_size, offset=pageNum * result_size)['items'] # Retrieves the designated page of user tracks

        return render_template("get-tracks.html", saved_tracks=saved_tracks, total_tracks=total_tracks, pageNum=pageNum)
    else:
        pageNum = 0 # Default value for initially loaded page
        session["track_pageNum"] = pageNum # Sets the session's page number

        saved_tracks = sp.current_user_saved_tracks(limit=result_size, offset=0)['items'] # Retrieves the designated page of user tracks

        return render_template("get-tracks.html", saved_tracks=saved_tracks, total_tracks=total_tracks, pageNum=pageNum)


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
        
        # Parses whether playlis is public or not
        if playlist_options['public'] == 'on':
            playlist_options['public'] = True
        else:
            playlist_options['public'] = False

        # Creates the playlist in the user's library
        # sp.user_playlist_create(session['username'], name, public=pub, description=desc)

        # Gets new playlist information from Spotify
        #sp.playlist

        # Tries to get playlist art
        try:
            playlist_art = playlist['images'][0]['url']
        except:
            playlist_art = ''

        session['playlist_options'] = playlist_options

        return redirect(url_for("new_playlist_options"))
    else:
        return render_template("playlist-new.html")


# Displays options for the creation of a new smart playlist
@app.route("/playlist-new/options", methods=["GET", "POST"])
@login_required
def new_playlist_options():
    if request.method == "POST":
        sp = create_sp() # Creates a new spotify object
        playlist_options = session['playlist_options']
        playlist_options.update({'source': []}) # Initializes the list of sources the user wants to pull songs from

        # Global preferences 
        playlist_options.update({"size": request.form.get("playlist_size")}) # Number of songs in playlist
        playlist_options['source'].append(request.form.get("source")) # Outputs the playlist ID

        # Simple Preferences 
        playlist_options.update({"mood": request.form.get("mood")})
        playlist_options.update({"vocal": request.form.get("vocal")})
        playlist_options.update({"hype": request.form.get("hype")})

        # Advanced Preferences 
        # Mood
        playlist_options.update({"mode": request.form.get("mode")}) # (0/1) Mode = Minor/Major
        playlist_options.update({"key": request.form.get("key")}) # Uses pitch-class notation (e.g. 0 = C, 1 = C#, 2= D)
        playlist_options.update({"valence": request.form.get("valence")}) # (0-1)'positiveness/happiness' of track

        # Vocal
        playlist_options.update({"speechiness": request.form.get("speechiness")}) # (0-1) Presence of spoken word (> 0.66 = All spoken word, 0.33 < semi-spoken < 0.66, All instruments < 0.33)
        playlist_options.update({"instrumentalness": request.form.get("instrumentalness")}) # (0-1) Absence of spoken word (> 0.5 is high confidence)

        # Hype
        playlist_options.update({"loudness": request.form.get("loudness")}) # (-60 - 0) How loud a track is overall
        playlist_options.update({"energy": request.form.get("energy")}) # (0-1) Energy brooooo
        
        # Other
        playlist_options.update({"danceability": request.form.get("danceability")}) # (0-1) How easy it is to dance to
        playlist_options.update({"acousticness": request.form.get("acousticness")}) # (0-1) Confidence of how acoustic a track is
        playlist_options.update({"liveness": request.form.get("liveness")}) # (0-1) Probability of track being played live
        playlist_options.update({"tempo": request.form.get("tempo")}) # TODO Find out tempo range
        playlist_options.update({"avg_duration": request.form.get("avg_duration")}) # Average song duration
        playlist_options.update({"total_duration": request.form.get("total_duration")}) # Total playlist duration #TODO Create formula for deviation from user specified value

        # Parses whether playlist is major or minor
        if playlist_options['mode'] == 'on':
            playlist_options['mode'] = 1
        else:
            playlist_options['mode'] = 0

        # TODO Make sure simple and advanced preferences are mutually exclusive
        session['playlist_options'] = playlist_options # Stores the new playlist's options in the session

        return redirect(url_for("new_playlist_create"))
    else:
        playlists = get_playlists()

        return render_template("playlist-new-options.html", playlists=playlists)


# Prompts for final options and creates the user-generated smart playlist
@app.route("/playlist-new/create", methods=["GET", "POST"])
@login_required
def new_playlist_create():
    sp = create_sp() # Creates a new spotify object
    playlist_options = session['playlist_options']

    # Conversion values
    key = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    mode = ['Major', 'Minor']

    if request.method == "POST":
        # Creates a new empty playlist with user parameters
        sp.user_playlist_create(session['username'], playlist_options['name'], public=session['playlist_options']['public'], description=session['playlist_options']['description'])
        total_tracks = [] # Tracks from every source the user specified
        total_tracks_sifted = [] # Total tracks that match user parameters

        # If the user specifies their liked tracks
        if 'liked songs' in playlist_options['source']:
            # Gets all of the user's liked tracks
            batch = sp.current_user_saved_tracks(limit=50, offset=0)['items']
            batchIterator = 0

            while batch:
                for track in batch:
                    total_tracks.append(track)

                batchIterator += 1
                batch = sp.current_user_saved_tracks(limit=50, offset=batchIterator*50)['items']
        
        print("[][][][][][][][][][][][][][][][][][][][][][][][]")
        print(len(playlist_options['source']))
        print(playlist_options['source'])
        print("[][][][][][][][][][][][][][][][][][][][][][][][]")

        # If the user specifies a playlist
        # TODO Add functionality for multiple playlists to act as sources
        if len(playlist_options['source']) > 1 or 'liked songs' not in playlist_options['source']:
            # Gets the tracks off of a specific playlist
            batch = sp.playlist_tracks(playlist_options['source'][0], limit=100, offset=0)['items']
            batchIterator = 0

            while batch:
                for track in batch:
                    total_tracks.append(track)

                batchIterator += 1
                batch = sp.playlist_tracks(playlist_options['source'][0], limit=100, offset=batchIterator*100)['items']
    
        # Gets tracks with user parameters
        batch = []
        batchIterator = 0

        # Loops through the tracks to find ones with similar parameters to what the user wants
        for track in total_tracks:
            if track['track']['id'] != None:
                batch.append(track['track']['id'])
            batchIterator += 1

            if batchIterator % 100 == 0 and batch != None:
                track_features = sp.audio_features(tracks=batch)
                batchIterator = 0
                batch = []

                # Loops through audio features and adds tracks that match user parameters
                for track_feature in track_features:
                    if int(track_feature['key']) == int(playlist_options['key']):
                        total_tracks_sifted.append(track_feature['id'])
        
        # Gets last track features (< 100)
        track_features = sp.audio_features(tracks=batch)
        for track_feature in track_features:
            if int(track_feature['key']) == int(playlist_options['key']):
                total_tracks_sifted.append(track_feature['id'])

        # Adds tracks to playlist
        batch = []

        for batchIterator in range(len(total_tracks_sifted)):
            batch.append(total_tracks_sifted[batchIterator])
            batchIterator += 1 

            if batchIterator % 100 == 0:
                sp.user_playlist_add_tracks(session['username'], sp.current_user_playlists(limit=1, offset=0)['items'][0]['id'], batch, position=None)
                batch = []
        
        # Adds remaining tracks (< 100)
        sp.user_playlist_add_tracks(session['username'], sp.current_user_playlists(limit=1, offset=0)['items'][0]['id'], batch, position=None)

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
    temp = sp.playlist(playlist_id)

    # Tries to get playlist art
    try:
        playlist_art = temp['images'][0]['url']
    except:
        playlist_art = ''

    # Parses playlist information into a list
    playlist = {'playlist_id': playlist_id, 'playlist_name': temp['name'], 
                'playlist_art': playlist_art, 'playlist_link': temp['external_urls']['spotify'], 
                'tracks': []}
    
    # Gets tracks on the playlist
    for i in temp['tracks']['items']:
        playlist['tracks'].append(i)
        print(playlist['tracks'])

    return render_template("playlist-edit-specific.html", playlist=playlist)