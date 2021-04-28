# SPOTIHELP
# Brendan Flisk 2021
# ------------------
# Allows the user to have more advanced control 
# over their spotify library and experience
#


import os
import sys
import time
import path
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

    # Gets current user's identifying information
    sp = create_sp()

    # Passes identifying info into user's session
    session["username"] = sp.current_user()['display_name'] # Sets session username
    session["user_id"] = db.execute("SELECT id FROM users WHERE username=?", session["username"])[0]['id'] # Sets session user id

    # Checks if the user is registered and adds to database accordingly
    if not db.execute("SELECT * FROM users WHERE username=?", session["username"]):
        db.execute('INSERT INTO users (username) VALUES (?);', session["username"])
        
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
@app.route("/playlist-new")
@login_required
def new_playlist():
    sp = create_sp() # Creates a new spotify object  

    return render_template("playlist-new.html")


# Allows the user to edit existing playlists
@app.route("/playlist-edit", methods=["GET", "POST"])
@login_required
def edit_playlist():
    if request.method == "POST":
        sp = create_sp()
        playlist_id = request.form.get("playlist")
        temp = sp.playlist(playlist_id)

        # Tries to get playlist art
        try:
            playlist_art = temp['images'][0]['url']
        except:
            playlist_art = ''

        playlist = {'playlist_id': playlist_id, 'playlist_name': temp['name'], 
                    'playlist_art': playlist_art, 'playlist_link': temp['external_urls']['spotify'], 
                    'tracks': []}
        
        for i in temp['tracks']['items']:
            playlist['tracks'].append(i)
            print(playlist['tracks'])

        return render_template("playlist-edit.html", playlists=None, playlist=playlist, specific_playlist=True)
    else:
        # Gets the user's playlists
        sp = create_sp()
        playlists = []
        
        # Checks whether the user's playlists have been saved in the database yet and retrieves them
        if not db.execute("SELECT * FROM playlists WHERE user_id=?;", session['user_id']):
            # Gets initial batch of playlists from spotify
            i = 0
            batch = sp.current_user_playlists(limit=50, offset=i*50)['items']

            # Loops through all user-saved playlists 50 at a time
            while batch:

                # Loops through current batch of playlists and adds user-created playlists into database
                for playlist in batch:
                    if playlist['owner']['id'] == session['username']:
                        # Tries to get playlist art
                        try:
                            playlist_art = playlist['images'][0]['url']
                        except:
                            playlist_art = ''

                        # Adds playlist into database
                        db.execute("INSERT INTO playlists VALUES (?,?,?,?,?);", session['user_id'], playlist['id'], playlist['name'], 
                                  playlist_art, playlist['external_urls']['spotify'])  

                # Continues iterating over all user playlists  
                i += 1
                batch = sp.current_user_playlists(limit=50, offset=i*50)['items']

        # Retrieves user's playlists from database       
        playlists = db.execute("SELECT * FROM playlists WHERE user_id=?;", session['user_id'])

        return render_template("playlist-edit.html", playlists=playlists, playlist=None, specific_playlist=False)
