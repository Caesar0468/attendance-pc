import io
from datetime import datetime

import piexif
from PIL import Image


def _to_exif_datetime(timestamp: str) -> str:
    """Convert an ISO timestamp to EXIF's required 'YYYY:MM:DD HH:MM:SS' format."""
    clean_ts = timestamp.replace("Z", "").split("+")[0].strip()
    candidates = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
    )
    for fmt in candidates:
        try:
            dt = datetime.strptime(clean_ts, fmt)
            return dt.strftime("%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(clean_ts)
        return dt.strftime("%Y:%m:%d %H:%M:%S")
    except ValueError:
        return datetime.now().strftime("%Y:%m:%d %H:%M:%S")


def embed_exif(image_bytes: bytes, username: str, timestamp: str) -> bytes:
    """Embed uploader metadata into image EXIF before saving."""
    img = Image.open(io.BytesIO(image_bytes))

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