import displays
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import secrets

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=secrets.spotify_client_id(),
    client_secret=secrets.spotify_client_secret(),
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-read-currently-playing"
))

img = displays.date_weather_spotify(sp)
img.save("output_image.png")