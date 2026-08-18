import subprocess


def capture_image(filename, exposure_us, gain, camera_config, width=None, height=None):
    cmd = [
        "rpicam-still",
        "--output", str(filename),
        "--shutter", str(int(exposure_us)),
        "--gain", str(float(gain)),
        "--immediate",
        "--nopreview"
    ]

    add_white_balance_args(cmd, camera_config)

    if width and height:
        cmd += ["--width", str(width), "--height", str(height)]

    subprocess.run(cmd, check=True)


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