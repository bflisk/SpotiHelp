import os
import sys
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from os import environ

import spotipy
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


# Application

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


# Has the user log in and authorize SpotiHelp to use information from Spotify
@app.route("/login")
def login():
    sp_oauth = create_spotify_oauth() # Creates a new sp_oauth object everytime a user logs in
    auth_url = sp_oauth.get_authorize_url() # Passes the authorization url into a variable

    return redirect(auth_url) # Redirects user to the authorization url


@app.route("/redirect")
def redirectPage():
    sp_oauth = create_spotify_oauth()
    session.clear() # Gets rid of current session
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info # Saves token info into the the session
    print(session["token_info"])

    # Tries to get token data. If it doesn't succeed, returns user back to index page
    try:
        token_info = get_token()
    except:
        print("-- User not logged in! --")
        return redirect(url_for("index", _external=False))

    return redirect(url_for("index", _external=False))


# Gets user tracks
# TODO Require user log-in
@app.route("/get-tracks")
def getTracks():
    # Tries to get token data. If it doesn't succeed, returns user back to index page
    try:
        token_info = get_token()
    except:
        print("-- User not logged in! --")
        return redirect(url_for("index", _external=False))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    saved_tracks = sp.current_user_saved_tracks(limit=1, offset=0)

    #return render_template("get-tracks.html", saved_tracks=saved_tracks)
    return saved_tracks['items']['track']['name']


# Allows the user to create new smart playlists
@app.route("/playlist-new", methods=["GET", "POST"])
def new_playlist():
    return render_template("playlist-new.html")


# Allows the user to edit existing playlists
@app.route("/playlist-edit", methods=["GET", "POST"])
def edit_playlist():
    return render_template("playlist-edit.html")


# Creates a spotify authorization object
def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=url_for('redirectPage',_external=True),
        scope="""user-library-read ugc-image-upload user-read-recently-played user-read-playback-state 
        user-top-read app-remote-control playlist-modify-public user-modify-playback-state playlist-modify-private
        user-follow-modify user-read-currently-playing user-follow-read user-library-modify
        user-read-playback-position playlist-read-private user-read-email user-read-private
        user-library-read playlist-read-collaborative streaming""")


# Processes the session token and refreshes it if needed
def get_token():
    token_info = session.get("token_info", None) # Gives token information if it exists, otherwise given 'None'

    # Checks if token_info is 'None'
    if not token_info:
        return redirect(url_for("index", _external=True))
    else:
        return token_info
    
    now = int(time.time()) # Gets current time
    is_expired = token_info['expires_at'] - now < 60 # T or F depending on condition

    # If the token is close to expiring, refresh it
    if is_expired:
        sp_oauth = create_spotify_oauth() 
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info