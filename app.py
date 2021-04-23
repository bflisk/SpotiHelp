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
from flask import Flask, flash, redirect, render_template, request, session, url_for
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

    # Checks if token_info is 'None'
    if not token_info:
        return redirect(url_for("index", _external=True))
    
    # Checks if token is close to expiring
    now = int(time.time()) # Gets current time
    is_expired = token_info['expires_at'] - now < 60 # T or F depending on condition

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

        return render_template("index.html", var=results['artists']['items'])

    else:

        return render_template("index.html")


# Redirects user after logging in and adds them to the user database
@app.route("/redirect")
def redirectPage():
    sp_oauth = create_spotify_oauth() # Creates a new sp_oauth object

    # Gets token information from the response 
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info # Saves token info into the the session
    sp = spotipy.Spotify(auth=token_info['access_token']) # Parses spotify response information

    username = sp.current_user()['display_name'] # Gets current user's username

    # Checks if the user is registered and adds to database accordingly
    if not db.execute("SELECT * FROM users WHERE username=?", username):
        db.execute('INSERT INTO users (username) VALUES (?);', username)

    session["user_id"] = db.execute("SELECT id FROM users WHERE username=?", username) # Sets session user id

    # Tries to get token data. If it doesn't succeed, returns user back to index page
    try:
        token_info = get_token()
    except:
        return redirect(url_for("index", _external=True))

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
    if request.method == "POST":
        # Tries to get token data. If it doesn't succeed, returns user back to index page
        try:
            token_info = get_token()
        except:
            print("-- User not logged in! --")
            return redirect(url_for("login"))
        
        try:
            sp = spotipy.Spotify(auth=token_info['access_token'])
        except:
            print(' WAAAAdfgtyytessssssssssssssssssssssssssssssssssssssssss')
            return redirect(url_for("login"))

        pageNum = int(request.form.get("pageNum"))
        pageNum += int(request.form.get("page")) # Gets page number user wants to be on
        if pageNum < 0:
            pageNum = 0 
        
        saved_tracks = []
        saved_tracks.append(sp.current_user_saved_tracks(limit=20, offset=pageNum * 20)['items'])

        return render_template("get-tracks.html", saved_tracks=saved_tracks, pageNum=pageNum)
    else:
        # Tries to get token data. If it doesn't succeed, returns user back to index page
        try:
            token_info = get_token()
        except:
            print("-- User not logged in! --")
            return redirect(url_for("login"))
        
        try:
            sp = spotipy.Spotify(auth=token_info['access_token'])
        except:
            return redirect(url_for("login"))

        # Default values for initially loaded page
        saved_tracks = []
        pageNum = 0 

        print('-----------------------------------------------------------------------')
        print(token_info)
        print('-----------------------------------------------------------------------')

        saved_tracks.append(sp.current_user_saved_tracks(limit=20, offset=0)['items'])   

        return render_template("get-tracks.html", saved_tracks=saved_tracks, pageNum=pageNum)


# Allows the user to create new smart playlists
@app.route("/playlist-new")
def new_playlist():
    token_info = get_token()
    sp = spotipy.Spotify(auth=token_info['access_token'])

    return render_template("playlist-new.html")


# Allows the user to edit existing playlists
@app.route("/playlist-edit")
@login_required
def edit_playlist():
    token_info = get_token()
    sp = spotipy.Spotify(auth=token_info['access_token'])

    return render_template("playlist-edit.html")