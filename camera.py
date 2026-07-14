import subprocess


def capture_image(filename, exposure_us, gain, width=None, height=None):
    cmd = [
        "rpicam-still",
        "--output", str(filename),
        "--shutter", str(int(exposure_us)),
        "--gain", str(float(gain)),
        "--awbgains", "1.5,1.5",
        "--immediate",
        "--nopreview"
    ]

    if width and height:
        cmd += ["--width", str(width), "--height", str(height)]

    subprocess.run(cmd, check=True)
