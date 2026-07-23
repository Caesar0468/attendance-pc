import io

import piexif
from PIL import Image


def _to_exif_datetime(timestamp: str) -> str:
    """Convert an ISO-ish timestamp to EXIF's required 'YYYY:MM:DD HH:MM:SS' format.
    Falls back to the raw string if it can't be parsed, rather than raising.
    """
    from datetime import datetime

    candidates = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f")
    for fmt in candidates:
        try:
            dt = datetime.strptime(timestamp, fmt)
            return dt.strftime("%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return timestamp


def embed_exif(image_bytes: bytes, username: str, timestamp: str) -> bytes:
    """Embed uploader metadata into image EXIF before saving."""
    img = Image.open(io.BytesIO(image_bytes))

    # Read any existing EXIF from the ORIGINAL image before mode conversion,
    # since .convert() drops the .info dict and would lose it otherwise.
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    try:
        if img.info.get("exif"):
            exif_dict = piexif.load(img.info["exif"])
    except Exception:
        pass

    if img.mode != "RGB":
        img = img.convert("RGB")

    exif_dict.setdefault("0th", {})
    exif_dict.setdefault("Exif", {})
    exif_dict["0th"][piexif.ImageIFD.Artist] = username.encode("utf-8")
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = _to_exif_datetime(timestamp).encode("utf-8")

    out = io.BytesIO()
    exif_bytes = piexif.dump(exif_dict)
    img.save(out, format="JPEG", exif=exif_bytes, quality=92)
    return out.getvalue()