import os
import sys

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
app.config["SESSION_COOKIE_NAME"] = "Brendan's Cookie"

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


@app.route("/login")
def login():
    sp_oauth = create_spotify_oauth() # Creates a new sp_oauth object everytime a user logs in
    auth_url = sp_oauth.get_authorize_url() # Passes the authorization url into a variable

    return redirect(auth_url) # Redirects user to the authorization url


@app.route("/redirect")
def redirectPage():
    return "redirect"


@app.route("/getTracks")
def getTracks():
    return "Get Tracks TODO"


@app.route("/playlist-new", methods=["GET", "POST"])
def new_playlist():
    return render_template("playlist-new.html")


@app.route("/playlist-edit", methods=["GET", "POST"])
def edit_playlist():
    return render_template("playlist-edit.html")


def create_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=url_for('redirectPage',_external=True),
        scope="user-library-read",
        show_dialog=True)