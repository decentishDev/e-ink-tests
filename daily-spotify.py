import displays
import socket
import time
from inky.auto import auto

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import secrets

def wait_for_internet(host="8.8.8.8", port=53, timeout=5):
    while True:
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            print("Internet connection established.")
            return
        except OSError:
            print("Waiting for internet...")
            time.sleep(10)

# ---------------------------
# SET UP DISPLAY
# ---------------------------

inky_display = auto()
WIDTH, HEIGHT = inky_display.resolution

if (WIDTH, HEIGHT) != (600, 448):
    raise RuntimeError(f"Expected 600x448 display, detected {WIDTH}x{HEIGHT}")

inky_display.set_border(inky_display.BLACK)

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=secrets.spotify_client_id(), # secret :)
    client_secret=secrets.spotify_client_secret(),
    redirect_uri="http://127.0.0.1:8888/callback",
    scope="user-read-currently-playing",
    cache_path=".spotify-cache"
))

img = displays.date_weather_spotify(sp)
inky_display.set_image(img)
inky_display.show()