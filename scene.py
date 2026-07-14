from astral import LocationInfo
from astral.sun import elevation as sun_elevation
from astral.moon import elevation as moon_elevation
from astral.moon import phase as moon_phase


def moon_illumination_percent(now):
    """
    Astral moon phase:
      0   = new moon
      7   = first quarter
      14  = full moon
      21  = last quarter
      28  = new moon again

    This converts phase into approximate illumination percent.
    """
    phase = moon_phase(now.date())

    if phase <= 14:
        illumination = phase / 14
    else:
        illumination = (28 - phase) / 14

    return round(max(0, min(1, illumination)) * 100, 1)


def get_observer(config):
    location = LocationInfo(
        name=config["name"],
        region="",
        timezone=config["timezone"],
        latitude=config["latitude"],
        longitude=config["longitude"]
    )

    return location.observer


def sky_conditions(now, config):
    observer = get_observer(config)

    sun_alt = sun_elevation(observer, now)
    moon_alt = moon_elevation(observer, now)
    moon_illum = moon_illumination_percent(now)

    return {
        "sun_altitude": round(sun_alt, 2),
        "moon_altitude": round(moon_alt, 2),
        "moon_illumination": moon_illum
    }


def current_scene(now, config):
    sky = sky_conditions(now, config)

    sun_alt = sky["sun_altitude"]
    moon_alt = sky["moon_altitude"]
    moon_illum = sky["moon_illumination"]

    moon_is_bright = moon_alt > 5 and moon_illum >= 50
    moon_is_very_bright = moon_alt > 15 and moon_illum >= 75

    if sun_alt >= 6:
        scene = "day"

    elif 0 <= sun_alt < 6:
        scene = "golden_hour"

    elif -6 <= sun_alt < 0:
        scene = "civil_twilight"

    elif -12 <= sun_alt < -6:
        scene = "nautical_twilight"

    elif -18 <= sun_alt < -12:
        scene = "astro_twilight"

    else:
        if moon_is_very_bright:
            scene = "bright_moon_night"
        elif moon_is_bright:
            scene = "moonlit_night"
        else:
            scene = "night"

    return scene, sky