#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from camera import capture_image
from exposure import calculate_exposure
from image_stats import measure_brightness

from scene import current_scene

from zoneinfo import ZoneInfo

BASE = Path("/home/curdog/New_lapse")

CONFIG_FILE = BASE / "config.json"
ACTIVE_FILE = BASE / "active_config.json"

PHOTO_DIR = BASE / "photos"
PREVIEW_DIR = BASE / "previews"
LOG_DIR = BASE / "logs"

def last_settings_file(config):
  return LOG_DIR / f"last_settings_{config['scene_key']}.json"


def load_configuration(now):

    raw = json.loads(CONFIG_FILE.read_text())
    active = json.loads(ACTIVE_FILE.read_text())

    location_key = active["location"]

    if location_key not in raw["locations"]:
        raise ValueError(f"Unknown location: {location_key}")

    # Build the basic configuration first.
    # This contains the location information needed by Astral.
    base_config = {}

    base_config.update(raw["defaults"])
    base_config.update(raw["locations"][location_key])

    base_config["location_key"] = location_key


    if active.get("mode", "auto") == "auto":
        scene_key, sky = current_scene(now, base_config)
    else:
        scene_key = active["mode"]
        sky = {}

    config = {}

    config.update(raw["defaults"])
    config.update(raw["locations"][location_key])
    config.update(raw["scene_profiles"][scene_key])

    config["location_key"] = location_key
    config["scene_key"] = scene_key
    config["sky"] = sky

    return config

def ensure_directories():

    PHOTO_DIR.mkdir(exist_ok=True)
    PREVIEW_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)


def validate_clock(config):

    minimum = datetime.fromisoformat(config["min_valid_date"])

    if datetime.now() < minimum:
        print("Clock is invalid.")
        print("Please set the time before starting.")
        sys.exit(1)


def load_last_settings(config):

    path = last_settings_file(config)

    if path.exists():
        return json.loads(path.read_text())

    return {
        "exposure_us": config["starting_exposure_us"],
        "gain": config["starting_gain"]
    }


def save_last_settings(config, exposure, gain):

    path = last_settings_file(config)

    path.write_text(json.dumps({
        "scene": config["scene_key"],
        "exposure_us": exposure,
        "gain": gain
    }, indent=2))

def main():

    ensure_directories()

    raw = json.loads(CONFIG_FILE.read_text())
    active = json.loads(ACTIVE_FILE.read_text())

    location_key = active["location"]
    timezone_name = raw["locations"][location_key]["timezone"]

    now = datetime.now(ZoneInfo(timezone_name))

    config = load_configuration(now)

    validate_clock(config)

    previous = load_last_settings(config)

    timestamp = now.strftime("%Y%m%d_%H%M%S")

    preview = PREVIEW_DIR / f"preview_{timestamp}.jpg"

    capture_image(
        filename=preview,
        exposure_us=previous["exposure_us"],
        gain=previous["gain"],
        width=config["preview_width"],
        height=config["preview_height"]
    )

    brightness = measure_brightness(preview)

    exposure, gain = calculate_exposure(
        config,
        previous["exposure_us"],
        previous["gain"],
        brightness
    )

    photo = PHOTO_DIR / f"IMG_{timestamp}.jpg"

    capture_image(
        filename=photo,
        exposure_us=exposure,
        gain=gain
    )

    log = {

        "timestamp": now.isoformat(),

        "location": config["location_key"],
        "scene": config["scene_key"],

        "latitude": config["latitude"],
        "longitude": config["longitude"],
        
        "sky": config.get("sky", {}),

        "photo": str(photo),

        "preview": str(preview),

        "brightness": brightness,

        "previous_exposure": previous["exposure_us"],
        "previous_gain": previous["gain"],

        "new_exposure": exposure,
        "new_gain": gain,

        "scene": config["scene_key"]

    }

    logfile = LOG_DIR / f"IMG_{timestamp}.json"

    logfile.write_text(json.dumps(log, indent=4))

    save_last_settings(config, exposure, gain)

    print(f"{timestamp} captured successfully")


if __name__ == "__main__":
    main()
