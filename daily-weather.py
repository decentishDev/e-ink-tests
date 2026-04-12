#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import geocoder
import time
import os
import random
from PIL import Image, ImageDraw, ImageFont
from inky.auto import auto
from font_source_serif_pro import SourceSerifPro

import socket

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

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

session = requests_session()

main_font = SourceSerifPro
# ---------------------------
# CONFIG
# ---------------------------

CITY_NAME = "Madison, Wisconsin"
COUNTRYCODE = "US"
BACKGROUND_PATH = "images/background.png"

UNSPLASH_ACCESS_KEY = secrets.unsplash_access_key()


# ---------------------------
# UNSPLASH BACKGROUND FETCH
# ---------------------------

def fetch_unsplash_background(weather):

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
# SET UP DISPLAY
# ---------------------------

inky_display = auto()
WIDTH, HEIGHT = inky_display.resolution

if (WIDTH, HEIGHT) != (600, 448):
    raise RuntimeError(f"Expected 600x448 display, detected {WIDTH}x{HEIGHT}")

inky_display.set_border(inky_display.WHITE)


# ---------------------------
# WEATHER FUNCTIONS
# ---------------------------

def get_coords(address):
    g = geocoder.arcgis(address)
    return g.latlng


def get_weather(address):
    coords = get_coords(address)
    if coords is None:
        return None

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={coords[0]}&longitude={coords[1]}"
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


# ---------------------------
# FETCH WEATHER
# ---------------------------

location_string = f"{CITY_NAME}, {COUNTRYCODE}"

wait_for_internet()
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

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)


# Date
now = time.localtime()
day_with_suffix = ordinal(now.tm_mday)
today_date = time.strftime(f"%A, %B {day_with_suffix}", now)

date_bbox = condition_font.getbbox(today_date)
date_width = date_bbox[2] - date_bbox[0]
date_height = date_bbox[3] - date_bbox[1]

date_box = (30, 30, 30 + date_width, 30 + date_height)
date_color = get_contrasting_bw(img, date_box)

draw.text((30, 30), today_date,
          fill=date_color[0],
          font=condition_font,
	  stroke_width=1, stroke_fill=date_color[1])

# High / Low
high_text = f"{high_f:.0f}°F"
low_text = f"{low_f:.0f}°F"

x_start = 30
y_start = HEIGHT - 160 - 10

draw.text((x_start, y_start), high_text, fill=RED,
          font=highlow_font,
	  stroke_width=1, stroke_fill=WHITE)

high_width = highlow_font.getbbox(high_text)[2]

draw.text((x_start + high_width + 25, y_start), low_text,
          fill=BLUE, font=highlow_font,
	  stroke_width=1, stroke_fill=WHITE)


# Weather condition
condition_y = HEIGHT - 95 - 20

cond_bbox = condition_font.getbbox(weather_text)
cond_width = cond_bbox[2] - cond_bbox[0]
cond_height = cond_bbox[3] - cond_bbox[1]

cond_box = (30, condition_y,
            30 + cond_width,
            condition_y + cond_height)

cond_color = get_contrasting_bw(img, cond_box)

draw.text((30, condition_y), weather_text,
          fill=cond_color[0],
          font=condition_font,
	  stroke_width=1, stroke_fill=cond_color[1])

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

# Now compute color based on truncated text
desc_bbox = small_font.getbbox(image_description)
desc_width = desc_bbox[2] - desc_bbox[0]
desc_height = desc_bbox[3] - desc_bbox[1]

desc_box = (desc_x, desc_y,
            desc_x + desc_width,
            desc_y + desc_height)

desc_color = get_contrasting_bw(img, desc_box)

draw.text((desc_x, desc_y), image_description,
          fill=desc_color[0],
          font=small_font,
	  stroke_width=1, stroke_fill=desc_color[1])

# ---------------------------
# DISPLAY
# ---------------------------

inky_display.set_image(img)
inky_display.show()
