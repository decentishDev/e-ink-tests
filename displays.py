import requests
import time
import os
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
from font_source_serif_pro import SourceSerifPro

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import secrets

CITY_NAME = "Madison, Wisconsin"
COUNTRYCODE = "US"
BACKGROUND_PATH = "images/background.png"

UNSPLASH_ACCESS_KEY = secrets.unsplash_access_key()

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

(WIDTH, HEIGHT) = (600, 448)

def requests_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ---------------------------
# UNSPLASH BACKGROUND FETCH
# ---------------------------

def fetch_unsplash_background(weather):

    session = requests.Session()

    query_options = [
	f"landscape {weather.lower()}",
        "wallpaper",
        "nature",
        "architecture"
    ]

    query = random.choice(query_options)

    print(query)

    url = "https://api.unsplash.com/search/photos"

    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
    }

    params = {
        "query": query,
        "orientation": "landscape",
        "content_filter": "high",
        "order_by": "relevant",
        "per_page": 20
    }

    #response = requests.get(url, headers=headers, params=params)
    response = session.get(url, headers=headers, params=params, timeout=20)

    if response.status_code != 200:
        print("Unsplash error:", response.status_code)
        print(response.text)
        return None

    results = response.json().get("results", [])

    if not results:
        print("No Unsplash results found.")
        return None

    # Pick a random relevant image
    data = random.choice(results)

    image_url = data["urls"]["regular"]

    description = data.get("description") or data.get("alt_description") or "Madison, Wisconsin"

    #img_response = requests.get(image_url)
    img_response = session.get(image_url, timeout=20)

    if img_response.status_code != 200:
        print("Failed to download image")
        return None

    if os.path.exists(BACKGROUND_PATH):
        os.remove(BACKGROUND_PATH)

    with open(BACKGROUND_PATH, "wb") as f:
        f.write(img_response.content)

    print("New background image downloaded.")

    return f"\"{description}\""

# ---------------------------
# WEATHER FUNCTIONS
# ---------------------------


def get_weather(address):
    session = requests.Session()

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude=43.0722&longitude=89.4008"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min"
        f"&timezone=auto"
    )

    #res = requests.get(url)
    res = session.get(url, timeout=20)

    if res.status_code != 200:
        print("Weather API error:", res.status_code)
        return None

    data = res.json()

    daily = data.get("daily", {})

    try:
        high_c = daily["temperature_2m_max"][0]
        low_c = daily["temperature_2m_min"][0]
        weathercode = daily["weathercode"][0]
    except (KeyError, IndexError):
        return None

    return {
        "high_c": high_c,
        "low_c": low_c,
        "weathercode": weathercode
    }



def ordinal(n):
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"

def get_contrasting_bw(image, bbox, threshold=100):
    """
    Given an image and a bounding box (x1, y1, x2, y2),
    compute average brightness and return BLACK or WHITE.
    """
    x1, y1, x2, y2 = bbox

    # Clamp to image bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(image.width, x2)
    y2 = min(image.height, y2)

    region = image.crop((x1, y1, x2, y2))
    pixels = list(region.getdata())

    if not pixels:
        return BLACK

    avg_r = sum(p[0] for p in pixels) / len(pixels)
    avg_g = sum(p[1] for p in pixels) / len(pixels)
    avg_b = sum(p[2] for p in pixels) / len(pixels)

    # Perceived luminance formula
    brightness = 0.299 * avg_r + 0.587 * avg_g + 0.114 * avg_b

    return (BLACK if brightness > threshold else WHITE, WHITE if brightness > threshold else BLACK)

def truncate_text_to_width(text, font, max_width, draw):
    """
    Truncate text so it fits within max_width (in pixels).
    Adds '...' if truncated.
    """
    if draw.textlength(text, font=font) <= max_width:
        return text

    ellipsis = "..."
    ellipsis_width = draw.textlength(ellipsis, font=font)

    truncated = text
    while truncated:
        truncated = truncated[:-1]
        if draw.textlength(truncated, font=font) + ellipsis_width <= max_width:
            return truncated + ellipsis

    return ellipsis


def draw_text_with_border(img, text, position, font, fill=(255, 255, 255), border_alpha=128):
    """
    Draw text with a soft semi-transparent black border.
    The border darkens the background slightly without clipping into the text.
    """
    x, y = position
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    border_color = (0, 0, 0, border_alpha)
    fill_color = (*fill, 255)
    offsets = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for dx, dy in offsets:
        overlay_draw.text((x + dx, y + dy), text, font=font, fill=border_color)

    overlay_draw.text((x, y), text, font=font, fill=fill_color)

    img_rgba = img.convert("RGBA")
    combined = Image.alpha_composite(img_rgba, overlay)
    img.paste(combined.convert("RGB"))


def date_weather_image():

    session = requests_session()

    main_font = SourceSerifPro

    # ---------------------------
    # FETCH WEATHER
    # ---------------------------

    location_string = f"{CITY_NAME}, {COUNTRYCODE}"

    weather = get_weather(location_string)

    if weather is None:
        raise RuntimeError("Could not fetch daily weather data.")

    high_f = (weather["high_c"] * 9 / 5) + 32
    low_f = (weather["low_c"] * 9 / 5) + 32
    weathercode = weather["weathercode"]


    weather_descriptions = {
        0: "Clear",
        1: "Mostly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Freezing fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        80: "Rain showers",
        95: "Thunderstorm"
    }

    weather_text = weather_descriptions.get(weathercode, "Unknown")

    image_description = fetch_unsplash_background(weather_text)
    if image_description is None:
        image_description = "Madison, Wisconsin"


    # ---------------------------
    # CREATE IMAGE
    # ---------------------------

    background = Image.open(BACKGROUND_PATH).convert("RGB")
    background = background.resize((WIDTH, HEIGHT))

    img = background.copy()
    draw = ImageDraw.Draw(img)

    highlow_font = ImageFont.truetype(main_font, 55)
    condition_font = ImageFont.truetype(main_font, 40)
    small_font = ImageFont.truetype(main_font, 20)


    # Date
    now = time.localtime()
    day_with_suffix = ordinal(now.tm_mday)
    today_date = time.strftime(f"%A, %B {day_with_suffix}", now)

    date_bbox = condition_font.getbbox(today_date)
    date_width = date_bbox[2] - date_bbox[0]
    date_height = date_bbox[3] - date_bbox[1]

    draw_text_with_border(img, today_date, (30, 30), condition_font)

    # High / Low
    high_text = f"{high_f:.0f}°F"
    low_text = f"{low_f:.0f}°F"

    x_start = 30
    y_start = HEIGHT - 160 - 10

    draw_text_with_border(img, high_text, (x_start, y_start), highlow_font, fill=RED)

    high_width = highlow_font.getbbox(high_text)[2]

    draw_text_with_border(img, low_text, (x_start + high_width + 25, y_start), highlow_font, fill=BLUE)


    # Weather condition
    condition_y = HEIGHT - 95 - 20

    cond_bbox = condition_font.getbbox(weather_text)
    cond_width = cond_bbox[2] - cond_bbox[0]
    cond_height = cond_bbox[3] - cond_bbox[1]

    draw_text_with_border(img, weather_text, (30, condition_y), condition_font)

    # ---------------------------
    # Image Description (LEFT under condition)
    # ---------------------------

    desc_y = condition_y + 45 + 10
    desc_x = 30
    right_margin = 30

    max_width = WIDTH - desc_x - right_margin

    # Truncate if necessary
    image_description = truncate_text_to_width(
        image_description,
        small_font,
        max_width,
        draw
    )

    # Draw the image description with a soft black border and white fill.
    draw_text_with_border(img, image_description, (desc_x, desc_y), small_font)
    return img



LAST_ALBUM_PATH = "last_album.jpg"

def date_weather_spotify(sp):

    session = requests_session()
    main_font = SourceSerifPro

    LEFT_WIDTH = int(WIDTH * 0.4)
    RIGHT_WIDTH = WIDTH - LEFT_WIDTH

    # ---------------------------
    # FETCH WEATHER
    # ---------------------------
    location_string = f"{CITY_NAME}, {COUNTRYCODE}"
    weather = get_weather(location_string)

    if weather is None:
        raise RuntimeError("Could not fetch daily weather data.")

    high_f = (weather["high_c"] * 9 / 5) + 32
    low_f = (weather["low_c"] * 9 / 5) + 32
    weathercode = weather["weathercode"]

    weather_descriptions = {
        0: "Clear",
        1: "Mostly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Freezing fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        80: "Rain showers",
        95: "Thunderstorm"
    }

    weather_text = weather_descriptions.get(weathercode, "Unknown")

    # ---------------------------
    # FETCH SPOTIFY ALBUM ART
    # ---------------------------
    RIGHT_MARGIN = 20
    usable_width = RIGHT_WIDTH - RIGHT_MARGIN

    album_img = None

    try:
        current = sp.current_user_playing_track()

        if current and current.get("item"):
            track = current["item"]
        else:
            recent = sp.current_user_recently_played(limit=1)
            if not recent or not recent.get("items"):
                raise Exception("No recent tracks found")
            track = recent["items"][0]["track"]

        album = track["album"]
        image_url = album["images"][0]["url"]

        response = requests.get(image_url, timeout=20)
        response.raise_for_status()

        album_img = Image.open(BytesIO(response.content)).convert("RGB")
        album_img.save(LAST_ALBUM_PATH)

    except Exception as e:
        print("Spotify error:", e)

    # ---------------------------
    # LOAD FROM DISK IF NOTHING IS PLAYING
    # ---------------------------
    if album_img is None:
        if os.path.exists(LAST_ALBUM_PATH):
            album_img = Image.open(LAST_ALBUM_PATH).convert("RGB")
        else:
            album_img = Image.new("RGB", (usable_width, usable_width), (30, 30, 30))

    # Ensure square fit (no distortion)
    album_size = min(usable_width, HEIGHT)
    album_img = ImageOps.fit(album_img, (album_size, album_size), Image.LANCZOS)

    # ---------------------------
    # CREATE BACKGROUND (blurred album art)
    # ---------------------------
    bg = album_img.copy()

    scale = max(WIDTH / bg.width, HEIGHT / bg.height)
    bg = bg.resize((int(bg.width * scale), int(bg.height * scale)))

    left = (bg.width - WIDTH) // 2
    top = (bg.height - HEIGHT) // 2
    bg = bg.crop((left, top, left + WIDTH, top + HEIGHT))

    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
    bg = ImageEnhance.Brightness(bg).enhance(0.4)

    img = bg.copy()
    draw = ImageDraw.Draw(img)

    # ---------------------------
    # PLACE ALBUM ART (RIGHT SIDE)
    # ---------------------------
    x_offset = LEFT_WIDTH + (usable_width - album_size) // 2
    y_offset = (HEIGHT - album_size) // 2

    img.paste(album_img, (x_offset, y_offset))

    # ---------------------------
    # FONTS
    # ---------------------------
    weekday_font = ImageFont.truetype(main_font, 48)
    date_font = ImageFont.truetype(main_font, 32)
    temp_font = ImageFont.truetype(main_font, 32)
    condition_font = ImageFont.truetype(main_font, 36)

    # ---------------------------
    # DATE
    # ---------------------------
    now = time.localtime()
    weekday = time.strftime("%A", now)
    day_with_suffix = ordinal(now.tm_mday)
    date_line = time.strftime(f"%B {day_with_suffix}", now)

    x = 20
    y = 50

    draw.text((x, y), weekday, font=weekday_font, fill=WHITE)
    y += 55

    draw.text((x, y), date_line, font=date_font, fill=WHITE)
    y += 150

    # ---------------------------
    # TEMPERATURE
    # ---------------------------
    high_text = f"{high_f:.0f}°F"
    low_text = f"{low_f:.0f}°F"

    draw.text((x, y), high_text, font=temp_font, fill=RED)
    low_x = x + draw.textlength(high_text, font=temp_font) + 20
    draw.text((low_x, y), low_text, font=temp_font, fill=BLUE)
    y += 40

    # ---------------------------
    # WEATHER CONDITION
    # ---------------------------
    draw.text((x, y), weather_text, font=condition_font, fill=WHITE)

    return img