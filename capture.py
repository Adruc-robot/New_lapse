#!/usr/bin/env python3

import json
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from camera import capture_image
from exposure import calculate_exposure
from image_stats import measure_brightness
from scene import current_scene

BASE = Path("/home/curdog/New_lapse")

CONFIG_FILE = BASE / "config.json"
ACTIVE_FILE = BASE / "active_config.json"

PHOTO_DIR = BASE / "photos"
PREVIEW_DIR = BASE / "previews"
LOG_DIR = BASE / "logs"

LAST_SETTINGS_FILE = LOG_DIR / "last_settings.json"


# Built-in capture defaults. These apply when a camera/scene does not
# explicitly provide a capture profile value.
CAPTURE_DEFAULTS = {
    "settle_seconds": 0,
    "delay_between_images": 0,
    "measure_each_image": False,
}

SUPPORTED_CONDITIONS = {
    "sun_altitude",
    "moon_altitude",
    "moon_illumination",
}


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

    # Build the basic configuration first. This contains the location
    # information needed by Astral.
    base_config = {}
    base_config.update(raw["defaults"])
    base_config.update(raw["locations"][location_key])
    base_config["brightness_model"] = raw["brightness_model"]
    base_config["camera_limits"] = raw["camera_limits"]
    base_config["location_key"] = location_key

    profile = active.get("profile", active.get("mode", "auto"))

    detected_scene, sky = current_scene(now, base_config)

    if profile == "auto":
        scene_key = detected_scene
    else:
        scene_key = profile

    if scene_key not in raw["scene_profiles"]:
        raise ValueError(
            f"Scene '{scene_key}' has no scene_profiles entry in config.json"
        )

    config = dict(base_config)
    config.update(raw["defaults"])
    config.update(raw["locations"][location_key])
    config.update(raw["scene_profiles"][scene_key])

    config["location_key"] = location_key
    config["camera_key"] = camera_key
    config["scene_key"] = scene_key
    config["sky"] = sky
    config["camera"] = camera

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
        "gain": config["starting_gain"],
    }


def save_last_settings(scene_key, exposure, gain):
    LAST_SETTINGS_FILE.write_text(
        json.dumps(
            {
                "scene": scene_key,
                "exposure_us": exposure,
                "gain": gain,
            },
            indent=2,
        )
    )


def condition_matches(actual_value, condition):
    """Return True when an observed sky value satisfies a min/max condition."""
    if not isinstance(condition, dict):
        raise ValueError("Capture-profile conditions must be objects with min/max")

    minimum = condition.get("min")
    maximum = condition.get("max")

    if minimum is not None and actual_value < minimum:
        return False

    if maximum is not None and actual_value > maximum:
        return False

    return True


def profile_matches(profile, sky):
    """All configured conditions must match. No conditions means fallback match."""
    conditions = profile.get("conditions")

    if not conditions:
        return True

    for condition_name, condition in conditions.items():
        if condition_name not in SUPPORTED_CONDITIONS:
            raise ValueError(
                f"Unsupported capture-profile condition: {condition_name}"
            )

        if condition_name not in sky:
            return False

        if not condition_matches(sky[condition_name], condition):
            return False

    return True


def select_capture_profile(config):
    """
    Resolve the active camera's capture profile for the current scene.

    Profiles are evaluated in config order. First matching profile wins.
    If the camera or scene has no capture profile, normal single-image capture
    is used via CAPTURE_DEFAULTS.
    """
    camera = config.get("camera", {})
    capture_profiles = camera.get("capture_profiles", {})
    scene_profiles = capture_profiles.get(config["scene_key"])

    if scene_profiles is None:
        return dict(CAPTURE_DEFAULTS)

    # The agreed schema uses a list, but accepting one object makes the loader
    # tolerant of simple/legacy configurations.
    if isinstance(scene_profiles, dict):
        scene_profiles = [scene_profiles]

    if not isinstance(scene_profiles, list):
        raise ValueError(
            f"camera.capture_profiles.{config['scene_key']} must be a list"
        )

    for profile in scene_profiles:
        if profile_matches(profile, config.get("sky", {})):
            resolved = dict(CAPTURE_DEFAULTS)
            resolved.update(profile)
            return resolved

    # No matching conditional profile is equivalent to no special behavior.
    return dict(CAPTURE_DEFAULTS)


def camera_config_for_capture(base_camera_config, profile=None, step=None):
    """Resolve AWB overrides: step > profile > camera.py's built-in default."""
    camera_config = deepcopy(base_camera_config)

    # capture_profiles are instructions for capture.py, not rpicam-still.
    camera_config.pop("capture_profiles", None)

    if profile and "awb" in profile:
        camera_config["awb"] = deepcopy(profile["awb"])

    if step and "awb" in step:
        camera_config["awb"] = deepcopy(step["awb"])

    return camera_config


def validate_non_negative_integer(name, value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def validate_capture_profile(profile):
    validate_non_negative_integer(
        "settle_seconds", profile.get("settle_seconds", 0)
    )
    validate_non_negative_integer(
        "delay_between_images", profile.get("delay_between_images", 0)
    )

    measure_each_image = profile.get("measure_each_image", False)
    if not isinstance(measure_each_image, bool):
        raise ValueError("measure_each_image must be boolean")

    sequence = profile.get("sequence")
    if sequence is None:
        return

    repeat = sequence.get("repeat", 1)
    if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 1:
        raise ValueError("sequence.repeat must be an integer >= 1")

    steps = sequence.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise ValueError("sequence.steps must be a non-empty list")

    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("Each sequence step must be an object")

        label = step.get("label")
        if label is not None and (
            not isinstance(label, str)
            or not label
            or not label.replace("_", "").isalnum()
        ):
            raise ValueError(
                "sequence step label must be non-empty alphanumeric/underscore"
            )

        exposure_us = step.get("exposure_us")
        if exposure_us is not None and (
            not isinstance(exposure_us, int)
            or isinstance(exposure_us, bool)
            or exposure_us <= 0
        ):
            raise ValueError("sequence step exposure_us must be an integer > 0")

        gain = step.get("gain")
        if gain is not None and (
            not isinstance(gain, (int, float))
            or isinstance(gain, bool)
            or gain <= 0
        ):
            raise ValueError("sequence step gain must be a number > 0")


def capture_and_record(
    *,
    filename,
    exposure_us,
    gain,
    camera_config,
    settle_seconds=0,
    label=None,
    repeat_index=None,
    step_index=None,
    measure=False,
):
    
    camera_metadata = capture_image(
        filename=filename,
        exposure_us=exposure_us,
        gain=gain,
        camera_config=camera_config,
        settle_seconds=settle_seconds,
    )

    record = {
        "file": str(filename),
        "exposure_us": int(exposure_us),
        "gain": gain,
        "effective_exposure": exposure_us * gain,
    }
    record["camera_metadata"] = camera_metadata

    if label is not None:
        record["label"] = label

    if repeat_index is not None:
        record["repeat"] = repeat_index

    if step_index is not None:
        record["step"] = step_index

    awb = camera_config.get("awb")
    if awb is not None:
        record["awb"] = deepcopy(awb)

    if measure:
        record["brightness"] = measure_brightness(filename)

    return record


def capture_final_images(config, profile, timestamp, controller_exposure, controller_gain):
    """Execute either normal single capture or the configured sequence."""
    validate_capture_profile(profile)

    settle_seconds = profile.get("settle_seconds", 0)
    delay_between_images = profile.get("delay_between_images", 0)
    measure_each_image = profile.get("measure_each_image", False)
    sequence = profile.get("sequence")

    photos = []

    if sequence is None:
        photo = PHOTO_DIR / f"IMG_{timestamp}.jpg"
        camera_config = camera_config_for_capture(config["camera"], profile=profile)

        photos.append(
            capture_and_record(
                filename=photo,
                exposure_us=controller_exposure,
                gain=controller_gain,
                camera_config=camera_config,
                settle_seconds=settle_seconds,
                measure=measure_each_image,
            )
        )

        return photos

    repeat = sequence.get("repeat", 1)
    steps = sequence["steps"]
    total_images = repeat * len(steps)
    image_number = 0

    for repeat_index in range(1, repeat + 1):
        for step_index, step in enumerate(steps, start=1):
            image_number += 1

            exposure_us = step.get("exposure_us", controller_exposure)
            gain = step.get("gain", controller_gain)
            label = step.get("label", f"step{step_index}")

            if repeat > 1:
                suffix = f"{label}_{repeat_index:02d}"
            else:
                suffix = label

            photo = PHOTO_DIR / f"IMG_{timestamp}_{suffix}.jpg"
            camera_config = camera_config_for_capture(
                config["camera"], profile=profile, step=step
            )

            photos.append(
                capture_and_record(
                    filename=photo,
                    exposure_us=exposure_us,
                    gain=gain,
                    camera_config=camera_config,
                    settle_seconds=settle_seconds,
                    label=label,
                    repeat_index=repeat_index if repeat > 1 else None,
                    step_index=step_index,
                    measure=measure_each_image,
                )
            )

            if delay_between_images and image_number < total_images:
                time.sleep(delay_between_images)

    return photos


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

    # Resolve the capture profile before taking the preview so the preview uses
    # the same profile-level AWB as the final images.
    capture_profile = select_capture_profile(config)
    validate_capture_profile(capture_profile)

    preview = PREVIEW_DIR / f"preview_{timestamp}.jpg"
    preview_camera_config = camera_config_for_capture(
        config["camera"], profile=capture_profile
    )

    preview_metadata = capture_image(
        filename=preview,
        exposure_us=previous["exposure_us"],
        gain=previous["gain"],
        camera_config=preview_camera_config,
        width=config["preview_width"],
        height=config["preview_height"],
        settle_seconds=capture_profile.get("settle_seconds", 0),
    )
    brightness = measure_brightness(preview)

    exposure, gain, controller = calculate_exposure(
        config,
        previous["exposure_us"],
        previous["gain"],
        brightness,
    )

    photos = capture_final_images(
        config,
        capture_profile,
        timestamp,
        exposure,
        gain,
    )

    log = {
        "timestamp": now.isoformat(),
        "location": config["location_key"],
        "camera_key": config["camera_key"],
        "scene": config["scene_key"],
        "latitude": config["latitude"],
        "longitude": config["longitude"],
        "sky": config.get("sky", {}),
        "capture_profile": capture_profile,
        "photos": photos,
        "preview": str(preview),
        "preview_metadata": preview_metadata,
        "brightness": brightness,
        "camera": {
            "previous": {
                "exposure": previous["exposure_us"],
                "gain": previous["gain"],
                "effective_exposure": (
                    previous["exposure_us"] * previous["gain"]
                ),
            },
            "current": {
                "exposure": exposure,
                "gain": gain,
                "effective_exposure": exposure * gain,
            }
        },
        "controller": controller,
    }

    logfile = LOG_DIR / f"IMG_{timestamp}.json"
    logfile.write_text(json.dumps(log, indent=4))

    # The adaptive controller state is based on the preview/controller result,
    # not any experimental sequence-step overrides.
    save_last_settings(config["scene_key"], exposure, gain)

    print(f"{timestamp} captured successfully")


if __name__ == "__main__":
    main()
