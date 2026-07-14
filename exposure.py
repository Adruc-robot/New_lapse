import json
from pathlib import Path

BASE = Path("/home/curdog/New_lapse")
LOG_DIR = BASE / "logs"
HISTORY_FILE = LOG_DIR / "exposure_history.json"


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def save_history(history):
    LOG_DIR.mkdir(exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def add_history_entry(exposure_us, gain, brightness):
    history = load_history()

    history.append({
        "exposure_us": exposure_us,
        "gain": gain,
        "median": brightness["median"],
        "mean": brightness["mean"],
        "clipped_low": brightness["clipped_low"],
        "clipped_high": brightness["clipped_high"]
    })

    history = history[-5:]

    save_history(history)


def smoothed_median(current_median):
    history = load_history()

    if not history:
        return current_median

    values = [entry["median"] for entry in history]
    values.append(current_median)

    return sum(values) / len(values)


def calculate_exposure(config, old_exposure_us, old_gain, brightness):
    target = config["target_median"]

    measured = max(smoothed_median(brightness["median"]), 1)

    raw_correction = target / measured

    max_step_up = config.get("max_step_up", 1.35)
    max_step_down = config.get("max_step_down", 0.65)

    correction = clamp(raw_correction, max_step_down, max_step_up)

    new_exposure = old_exposure_us * correction
    new_gain = old_gain

    new_exposure = clamp(
        new_exposure,
        config["min_exposure_us"],
        config["max_exposure_us"]
    )

    if new_exposure >= config["max_exposure_us"] and measured < target:
        gain_correction = clamp(raw_correction, 1.0, 1.25)
        new_gain = old_gain * gain_correction

    if measured > target and old_gain > config["min_gain"]:
        gain_correction = clamp(raw_correction, 0.8, 1.0)
        new_gain = old_gain * gain_correction

    new_gain = clamp(
        new_gain,
        config["min_gain"],
        config["max_gain"]
    )

    new_exposure = int(new_exposure)
    new_gain = round(new_gain, 2)

    add_history_entry(new_exposure, new_gain, brightness)

    return new_exposure, new_gain
