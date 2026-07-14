from PIL import Image, ImageStat


def measure_brightness(path):
    img = Image.open(path).convert("L")

    stat = ImageStat.Stat(img)
    mean = stat.mean[0]

    pixels = list(img.getdata())
    pixels.sort()

    count = len(pixels)
    median = pixels[count // 2]

    clipped_low = sum(1 for p in pixels if p <= 3) / count
    clipped_high = sum(1 for p in pixels if p >= 250) / count

    p10 = pixels[int(count * 0.10)]
    p90 = pixels[int(count * 0.90)]
    p95 = pixels[int(count * 0.95)]
    p99 = pixels[int(count * 0.99)]

    return {
        "mean": round(mean, 2),
        "median": median,
        "p10": p10,
        "p90": p90,
        "p95": p95,
        "p99": p99,
        "clipped_low": round(clipped_low, 5),
        "clipped_high": round(clipped_high, 5)
    }
