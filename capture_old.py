#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from camera_old import capture_image
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

LAST_SETTINGS_FILE = LOG_DIR / "last_settings.json"

def last_settings_file(config):
  #return LOG_DIR / f"last_settings_{config['scene_key']}.json"
  return LOG_DIR / f"last_settings.json"

def load_configuration(now):

    raw = json.loads(CONFIG_FILE.read_text())
    active = json.loads(ACTIVE_FILE.read_text())

    location_key = active["location"]
    camera_key = active["camera"]

    if location_key not in raw["locations"]:
        raise ValueError(f"Unknown location: {location_key}")

    if camera_key not in raw["cameras"]:
        raise ValueError(f"Unknown camera: {camera_key}")

    camera = raw["cameras"][camera_key]

    # Build the basic configuration first.
    # This contains the location information needed by Astral.
    base_config = {}

    base_config.update(raw["defaults"])
    base_config.update(raw["locations"][location_key])
    base_config["brightness_model"] = raw["brightness_model"]
    base_config["camera_limits"] = raw["camera_limits"]
    base_config["location_key"] = location_key


    # if active.get("mode", "auto") == "auto":
    #     scene_key, sky = current_scene(now, base_config)
    # else:
    #     scene_key = active["mode"]
    #     sky = {}
    profile = active.get("profile", active.get("mode", "auto"))

    detected_scene, sky = current_scene(now, base_config)

    if profile == "auto":
        scene_key = detected_scene
    else:
        scene_key = profile

    config = dict(base_config)

    config.update(raw["defaults"])
    config.update(raw["locations"][location_key])
    config.update(raw["scene_profiles"][scene_key])

    config["location_key"] = location_key
    config["camera_key"] = camera_key
    config["scene_key"] = scene_key
    config["sky"] = sky
    config["camera"] = camera
    print(config.keys())
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
    if LAST_SETTINGS_FILE.exists():
        return json.loads(LAST_SETTINGS_FILE.read_text())

    return {
        "exposure_us": config["starting_exposure_us"],
        "gain": config["starting_gain"]
    }


def save_last_settings(scene_key, exposure, gain):

    LAST_SETTINGS_FILE.write_text(json.dumps({
        "scene": scene_key,
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
        camera_config=config["camera"],
        width=config["preview_width"],
        height=config["preview_height"]
    )

    brightness = measure_brightness(preview)

    exposure, gain, controller = calculate_exposure(
        config,
        previous["exposure_us"],
        previous["gain"],
        brightness
    )

    # photo = PHOTO_DIR / f"IMG_{timestamp}.jpg"

    # capture_image(
    #     filename=photo,
    #     exposure_us=exposure,
    #     gain=gain
    # )
    photos = []

    #if config["scene_key"] == "night":
    if (
            config["scene_key"] == "night"
            and config["camera_key"] == "imx462"
    ):
        exposure_factors = [
            ("exp1", 0.5),
            ("exp2", 1.0),
            ("exp3", 4.0),
        ]

        #max_exposure = config["max_exp"]
        #max_exposure = config["max_exposure_us"]
        max_exposure = config["camera_limits"].get(
            "experimental_max_exposure_us",
            config["max_exposure_us"]
        )

        for label, factor in exposure_factors:
            bracket_exposure = int(exposure * factor)
            bracket_exposure = min(bracket_exposure, max_exposure)

            photo = PHOTO_DIR / f"IMG_{timestamp}_{label}.jpg"

            capture_image(
                filename=photo,
                exposure_us=bracket_exposure,
                gain=gain,
                camera_config=config["camera"],
            )

            photos.append({
                "label": label,
                "factor": factor,
                "file": str(photo),
                "exposure_us": bracket_exposure,
                "gain": gain,
                "effective_exposure": bracket_exposure * gain
            })

    else:
        photo = PHOTO_DIR / f"IMG_{timestamp}.jpg"

        capture_image(
            filename=photo,
            exposure_us=exposure,
            gain=gain,
            camera_config=config["camera"],
        )

        photos.append({
            "file": str(photo),
            "exposure": exposure,
            "gain": gain,
            "effective_exposure": exposure * gain
        })
    log = {

        "timestamp": now.isoformat(),

        "location": config["location_key"],
        "scene": config["scene_key"],

        "latitude": config["latitude"],
        "longitude": config["longitude"],
        
        "sky": config.get("sky", {}),
        "bracketing": {
            "enabled": config["scene_key"] == "night",
            "experimental_max_exposure_us": config["camera_limits"].get(
                "experimental_max_exposure_us"
            )
        },

        #"photo": str(photo),
        "photos": photos,

        "preview": str(preview),

        "brightness": brightness,

        "camera": {
            "previous": {
                "exposure": previous["exposure_us"],
                "gain": previous["gain"],
                "effective_exposure": (
                    previous["exposure_us"] * previous["gain"]
                )
            },
            "current": {

                "exposure": exposure,
                "gain": gain,
                "effective_exposure": ( exposure * gain)
            }
        },
        "scene": config["scene_key"],
        "controller": controller

    }

    logfile = LOG_DIR / f"IMG_{timestamp}.json"

    logfile.write_text(json.dumps(log, indent=4))

    save_last_settings(config["scene_key"], exposure, gain)

    print(f"{timestamp} captured successfully")


if __name__ == "__main__":
    main()
