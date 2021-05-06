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

from random import randrange
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
            db.execute("INSERT INTO playlists VALUES (?,?,?,?,?)", session['user_id'], playlist_info['id'], playlist_info['name'], playlist_info['external_urls']['spotify'], 0) # Inserts playlist into database

    playlists = db.execute("SELECT * FROM playlists WHERE user_id=?;", session['user_id']) # Gets updated list of playlists from database
    return playlists


# Sifts through songs to get ones with user parameters
def sift_tracks(track_feature, playlist_options):
    # Mood
    mode = int(track_feature['mode']) == int(playlist_options['mode']) # (0/1) Mode = Minor/Major
    key = str(track_feature['key']) in playlist_options['key'] # Uses pitch-class notation (e.g. 0 = C, 1 = C#, 2= D)
    valence = abs(track_feature['valence'] - float(playlist_options['valence'])) < 0.5 # (0-1)'positiveness/happiness' of track

    # Vocal
    speechiness = abs(track_feature['speechiness'] - float(playlist_options['speechiness'])) < 0.5 # (0-1) Presence of spoken word (> 0.66 = All spoken word, 0.33 < semi-spoken < 0.66, All instruments < 0.33)
    instrumentalness = abs(track_feature['instrumentalness'] - float(playlist_options['instrumentalness'])) < 0.5 # (0-1) Absence of spoken word (> 0.5 is high confidence)

    # Hype
    loudness = abs(track_feature['loudness'] - float(playlist_options['loudness'])) < 20 # (-60 - 0) How loud a track is overall
    energy = abs(track_feature['energy'] - float(playlist_options['energy'])) < 0.5 # (0-1) Energy brooooo
    
    # Other
    danceability = abs(track_feature['danceability'] - float(playlist_options['danceability'])) < 0.5 # (0-1) How easy it is to dance to
    acousticness = abs(track_feature['acousticness'] - float(playlist_options['acousticness'])) < 0.5 # (0-1) Confidence of how acoustic a track is
    liveness = abs(track_feature['liveness'] - float(playlist_options['liveness'])) < 0.5 # (0-1) Probability of track being played live
    tempo = abs(track_feature['tempo'] - float(playlist_options['tempo'])) < 20

    # Checks if every parameter is met and returns true or false
    allow = bool(mode * key * valence * speechiness * instrumentalness * loudness * energy * danceability * acousticness * liveness * tempo)
    return allow


# Calculates values for spotify from the "Simple options"
def calculate_advanced_options(simple_options):
    mood = int(simple_options[0])
    vocal = int(simple_options[1])
    hype = int(simple_options[2])

    # Calculates values based on "mood"
    if mood > 50:
        session['playlist_options']['mode'] = 1
    else:
        session['playlist_options']['mode'] = 0

    session['playlist_options']['valence'] = mood * 0.01

    # Calculates values based on "vocal"
    session['playlist_options']['speechiness'] = vocal * 0.01
    session['playlist_options']['instrumentalness'] = 1 - (vocal * 0.01)

    # Calculates values based on "hype"
    session['playlist_options']['loudness'] = hype * 0.01
    session['playlist_options']['energy'] = hype * 0.01

    return


# TODO Widens parameters if not enough songs are in the playlist based on user-defined values
def widen_parms():
    parm_change_amount = []


    return parm_change_amount


# Gets minimum/maximum value for an option
def get_bound(option, change):
    bound = {}

    # Calculates bounds based on user-defined parameter
    bound.update({'min': (float(session['playlist_options'][option]) - (change/2))})
    bound.update({'max': (float(session['playlist_options'][option]) + (change/2))})

    # Rounds values to acceptable levels
    bound['min'] = round(bound['min'], 3)
    bound['max'] = round(bound['max'], 3)

    # Makes sure that the bounds are valid
    if option == 'loudness':
        if bound['min'] < -60:
            bound['min'] = -60
        elif bound['max'] > 0:
            bound['max'] = 0
    elif option == 'tempo':
        if bound['min'] < 10:
            bound['min'] = 10
        elif bound['max'] > 300:
            bound['max'] = 300
    else:
        if bound['min'] < 0:
            bound['mid'] = 0
        elif bound['max'] > 1:
            bound['max'] = 1

    return bound


# Gets additional songs from Spotify
# TODO Add functionality to search fo multiple keys
# TODO Add functionality for min_duration_ms & max_duration_ms
def seed_more_tracks(limit, artists, genres, tracks):
    sp = create_sp()
    playlist_options = session['playlist_options']
    change = session['playlist_options']['change']
    results = []

    # Sets value to None if the list is empty
    if artists == []:
        artists = None
    elif genres == []:
        genres = None
    elif tracks == []:
        tracks = None   

    # If the user did not specify a change, sets it to zero
    for i in change:
        if not change[i]:
            change[i] = 0.4
    
    # If the user did not specify a mode, allows Spotify to search for any mode
    if not playlist_options['mode']:
        mode = [0, 1]
    else:
        mode = [playlist_options['mode'], playlist_options['mode']]

    # Fetches tracks from Spotify's recommendation system that match user parameters
    batch = sp.recommendations(seed_artists=artists, seed_genres=genres, seed_tracks=tracks, limit=limit, country=None, 
        target_key=playlist_options['key'][0], 
        min_mode=mode[0], max_mode=mode[1])['tracks'] 
    """target_valence=playlist_options['valence'], min_valence=get_bound('valence', change['valence'])['min'], max_valence=get_bound('valence', change['valence'])['max'], 
    target_speechiness=playlist_options['speechiness'], min_speechiness=get_bound('speechiness', change['speechiness'])['min'], max_speechiness=get_bound('speechiness', change['speechiness'])['max'], 
    target_instrumentalness=playlist_options['instrumentalness'], min_instrumentalness=get_bound('instrumentalness', change['instrumentalness'])['min'], max_instrumentalness=get_bound('instrumentalness', change['instrumentalness'])['max'], 
    target_loudness=playlist_options['loudness'], min_loudness=get_bound('loudness', change['loudness'])['min'], max_loudness=get_bound('loudness', change['loudness'])['max'], 
    target_energy=playlist_options['energy'], min_energy=get_bound('energy', change['energy'])['min'], max_energy=get_bound('energy', change['energy'])['max'], 
    target_danceability=playlist_options['danceability'], min_danceability=get_bound('danceability', change['danceability'])['min'], max_danceability=get_bound('danceability', change['danceability'])['max'], 
    target_acousticness=playlist_options['acousticness'], min_acousticness=get_bound('acousticness', change['acousticness'])['min'], max_acousticness=get_bound('acousticness', change['acousticness'])['max'], 
    target_liveness=playlist_options['liveness'], min_liveness=get_bound('liveness', change['liveness'])['min'], max_liveness=get_bound('liveness', change['liveness'])['max'], 
    target_tempo=playlist_options['tempo'], min_tempo=get_bound('tempo', change['tempo'])['min'], max_tempo=get_bound('tempo', change['tempo'])['max'])['tracks']"""

    for track in batch:
        results.append(track['id'])

    return results


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


@app.route("/error")
def error():
    return render_template("error.html")


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
# TODO Allow user to choose popularity of songs (Only if the source is Spotify)
# TODO Maybe allow user to use a set of artists or songs to seed a playlist
# TODO Allow user to NOT choods an option
@app.route("/playlist-new/options", methods=["GET", "POST"])
@login_required
def new_playlist_options():
    if request.method == "POST":
        sp = create_sp() # Creates a new spotify object
        playlist_options = session['playlist_options']

        # Required preferences
        playlist_options.update({"source": []}) # Initializes the list of sources the user wants to pull songs from
        playlist_options.update({"change": {}}) # Initializes the changes in options if not enough songs are added to the playlist
        playlist_options.update({"key": []}) # Stores the keys the user wants tracks to be in
        playlist_options.update({"genre": []}) # Sotres a list of genres the user wants to pull from

        # Global preferences 
        playlist_options.update({"size": int(request.form.get("size"))}) # Number of songs in playlist
        playlist_options["source"].append(request.form.get("source")) # Outputs the playlist ID
        playlist_options.update({"fill": request.form.get("fill")}) # Fills playlist with tracks from Spotify if user's sources don't have enough songs
        playlist_options.update({"strict": request.form.get("strict")}) # If true, widens search parameters if the user does not have enough songs in their library
        playlist_options["genre"].append(request.form.get("genre"))

        # Simple Preferences 
        playlist_options.update({"mood": request.form.get("mood")})
        playlist_options["change"].update({"mood": request.form.get("mood_change")})
        playlist_options.update({"vocal": request.form.get("vocal")})
        playlist_options["change"].update({"vocal": request.form.get("vocal_change")})      
        playlist_options.update({"hype": request.form.get("hype")})
        playlist_options["change"].update({"hype": request.form.get("hype_change")})

        # Advanced Preferences 
        # Mood
        playlist_options.update({"mode": request.form.get("mode")}) # (0/1) Mode = Minor/Major
        playlist_options["key"].append(request.form.get("key")) # Uses pitch-class notation (e.g. 0 = C, 1 = C#, 2= D)
        playlist_options.update({"valence": request.form.get("valence")}) # (0-1)'positiveness/happiness' of track
        playlist_options["change"].update({"valence": request.form.get("valence_change")})

        # Vocal
        playlist_options.update({"speechiness": request.form.get("speechiness")}) # (0-1) Presence of spoken word (> 0.66 = All spoken word, 0.33 < semi-spoken < 0.66, All instruments < 0.33)
        playlist_options["change"].update({"speechiness": request.form.get("speechiness_change")})
        playlist_options.update({"instrumentalness": request.form.get("instrumentalness")}) # (0-1) Absence of spoken word (> 0.5 is high confidence)
        playlist_options["change"].update({"instrumentalness": request.form.get("instrumentalness_change")})

        # Hype
        playlist_options.update({"loudness": request.form.get("loudness")}) # (-60 - 0) How loud a track is overall
        playlist_options["change"].update({"loudness": request.form.get("loudness_change")})
        playlist_options.update({"energy": request.form.get("energy")}) # (0-1) Energy brooooo
        playlist_options["change"].update({"energy": request.form.get("energy_change")})
        
        # Other
        playlist_options.update({"danceability": request.form.get("danceability")}) # (0-1) How easy it is to dance to
        playlist_options["change"].update({"danceability": request.form.get("danceability_change")})
        playlist_options.update({"acousticness": request.form.get("acousticness")}) # (0-1) Confidence of how acoustic a track is
        playlist_options["change"].update({"acousticness": request.form.get("acousticness_change")})
        playlist_options.update({"liveness": request.form.get("liveness")}) # (0-1) Probability of track being played live
        playlist_options["change"].update({"liveness": request.form.get("liveness_change")})
        playlist_options.update({"tempo": request.form.get("tempo")}) # TODO Find out tempo range
        playlist_options["change"].update({"tempo": request.form.get("tempo_change")})
        playlist_options.update({"avg_duration": request.form.get("avg_duration")}) # Average song duration
        playlist_options.update({"total_duration": request.form.get("total_duration")}) # Total playlist duration #TODO Create formula for deviation from user specified value

        # Parses whether playlist is major or minor
        if playlist_options['mode'] == 'on':
            playlist_options['mode'] = 1
        else:
            playlist_options['mode'] = 0

        # Parses HTML into the correct format
        if playlist_options['fill'] == 'on':
            playlist_options['fill'] = True
        else:
            playlist_options['fill'] = False

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
        total_tracks = [] # Tracks from every source the user specified
        total_tracks_sifted = [] # Total tracks that match user parameters


        # If the user used simple options instead of advanced options
        if playlist_options['mood'] != None:
            calculate_advanced_options([playlist_options['mood'], playlist_options['vocal'], playlist_options['hype']])
            playlist_options = session['playlist_options']


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


        # If the user specifies a playlist
        if len(playlist_options['source']) > 1 or 'liked songs' not in playlist_options['source']:
            for playlist_source in playlist_options['source']:
                if playlist_source != "liked songs":
                    # Gets the tracks off of a specific playlist
                    batch = sp.playlist_tracks(playlist_source, limit=100, offset=0)['items']
                    batchIterator = 0

                    while batch:
                        for track in batch:
                            total_tracks.append(track)

                        batchIterator += 1
                        batch = sp.playlist_tracks(playlist_source, limit=100, offset=batchIterator*100)['items']


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
                    if sift_tracks(track_feature, playlist_options):
                        total_tracks_sifted.append(track_feature['id'])


        # Checks that the number of tracks equals the playlist size the user specified
        # If there are too many tracks, delete the extras
        if len(total_tracks_sifted) > int(playlist_options['size']):
            limit = len(total_tracks_sifted) - int(playlist_options['size']) # Number of tracks needed to delete from the playlist

            # Removes tracks from the list at random until it hits the desired playlist size
            for i in range(limit):
                total_tracks_sifted.pop(randrange(len(total_tracks_sifted)))

        # If there are not enough tracks, seed more
        elif len(total_tracks_sifted) < int(playlist_options['size']) and playlist_options['fill']:
            limit = int(playlist_options['size']) - len(total_tracks_sifted) # Number of tracks needed to fill the playlist
            remaining = limit
            seeds = {'artists': [], 'genres': playlist_options['genre'], 'tracks': []} # Seeds used to get similar tracks from Spotify

            # Randomly chooses tracks to seed (Makes sure there are 5 total seed sources)
            if len(total_tracks_sifted) >= (5 - len(seeds['genres'])):
                seeds['tracks'] = [] # Clears the seeds  
                for i in range(5 - (len(seeds['genres'] + seeds['artists']))):
                    seeds['tracks'].append(total_tracks_sifted[randrange(len(total_tracks_sifted))])

            # Seeds tracks in batches of 100
            for i in range(limit):
                if i % 100 == 0:
                    total_tracks_sifted.extend(seed_more_tracks(100, seeds['artists'], seeds['genres'], seeds['tracks']))
                    remaining -= 100

            # Seeds remaining tracks
            if remaining > 0:
                total_tracks_sifted.extend(seed_more_tracks(remaining, seeds['artists'], seeds['genres'], seeds['tracks']))
            
            # TODO If there are not enough tracks and the user deselected the 'strict' options, widen parameters and seed more tracks. Otherwise, re-seed tracks and add unique ones
            # TODO Make sure to repopulate seeds['tracks'] every time to get new tracks. Experiment with fewer seed tracks maybe?

        # Gets last track features (< 100)
        track_features = sp.audio_features(tracks=batch)
        for track_feature in track_features:
            if sift_tracks(track_feature, playlist_options):
                total_tracks_sifted.append(track_feature['id'])


        # Creates a new empty playlist with user parameters
        new_playlist = sp.user_playlist_create(session['username'], playlist_options['name'], public=session['playlist_options']['public'], description=session['playlist_options']['description'])

        # Adds tracks to playlist
        batch = []

        for batchIterator in range(len(total_tracks_sifted)):
            batch.append(total_tracks_sifted[batchIterator])
            batchIterator += 1 

            # Adds tracks in batches of 100
            if batchIterator % 100 == 0:
                sp.user_playlist_add_tracks(session['username'], new_playlist['id'], batch, position=None)
                batch = []


        # Adds remaining tracks (< 100)
        if len(batch) > 0:
            sp.user_playlist_add_tracks(session['username'], new_playlist['id'], batch, position=None)
        
        return render_template("playlist-new-create.html", playlist_options=playlist_options, created=True)
    else:
        # If the user used simple options instead of advanced options
        if playlist_options['mood'] != None:
            calculate_advanced_options([playlist_options['mood'], playlist_options['vocal'], playlist_options['hype']])
            playlist_options = session['playlist_options']

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