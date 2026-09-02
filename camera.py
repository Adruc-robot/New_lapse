import json
import subprocess


def capture_image(
    filename,
    exposure_us,
    gain,
    camera_config,
    width=None,
    height=None,
    settle_seconds=0,
):
    metadata_file = filename.with_suffix(".metadata.tmp.json")
    cmd = [
        "rpicam-still",
        "--output", str(filename),
        "--shutter", str(int(exposure_us)),
        "--gain", str(float(gain)),
        "--nopreview",
        "--metadata", str(metadata_file),
        "--metadata-format", "json",
    ]

    # With --immediate, rpicam-still captures as soon as possible and the
    # camera algorithms do not get a settling period.  When settle_seconds is
    # configured, keep the camera running for that long before capture.
    if settle_seconds > 0:
        cmd += ["--timeout", str(int(settle_seconds * 1000))]
    else:
        cmd += ["--immediate"]

    add_white_balance_args(cmd, camera_config)

    if width and height:
        cmd += ["--width", str(width), "--height", str(height)]

    subprocess.run(cmd, check=True)

    metadata = json.loads(metadata_file.read_text())
    metadata_file.unlink()

    return metadata

def add_white_balance_args(cmd, camera_config):
    awb = camera_config.get("awb", {})
    awb_mode = awb.get("mode", "auto")

    if awb_mode == "manual":
        gains = awb.get("gains", [1.5, 1.5])

        cmd.extend([
            "--awbgains",
            f"{gains[0]},{gains[1]}"
        ])
    else:
        cmd.extend([
            "--awb",
            awb_mode
        ])
