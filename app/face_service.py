from dataclasses import dataclass

import cv2
import numpy as np
from insightface.app import FaceAnalysis


@dataclass
class DetectedFace:
    embedding: np.ndarray
    bbox: list[float]
    crop_bytes: bytes


class FaceService:
    _instance: "FaceService | None" = None

    def __init__(self) -> None:
        self._app: FaceAnalysis | None = None

    def _ensure_ready(self) -> FaceAnalysis:
        if self._app is None:
            self._app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            self._app.prepare(ctx_id=0, det_size=(640, 640))
        return self._app

    @classmethod
    def get(cls) -> "FaceService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _read_image(self, image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not read that photo, please try again.")
        return img

    def detect_faces(self, image_bytes: bytes) -> list[DetectedFace]:
        app = self._ensure_ready()
        img = self._read_image(image_bytes)
        faces = app.get(img)
        if not faces:
            return []

        results: list[DetectedFace] = []
        for face in faces:
            x1, y1, x2, y2 = [int(v) for v in face.bbox]
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            ok, encoded = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not ok:
                continue

            results.append(
                DetectedFace(
                    embedding=np.array(face.embedding, dtype=np.float32),
                    bbox=[float(x1), float(y1), float(x2), float(y2)],
                    crop_bytes=encoded.tobytes(),
                )
            )
        return results

    def get_single_embedding(self, image_bytes: bytes) -> np.ndarray:
        faces = self.detect_faces(image_bytes)
        if not faces:
            raise ValueError("No face found in that photo. Please use a clear front-facing photo.")
        if len(faces) > 1:
            raise ValueError("Multiple faces found. Please use a photo with only one person.")
        return faces[0].embedding

    def create_thumbnail(self, image_bytes: bytes, size: int = 128) -> bytes:
        app = self._ensure_ready()
        img = self._read_image(image_bytes)
        faces = app.get(img)
        if faces:
            x1, y1, x2, y2 = [int(v) for v in faces[0].bbox]
            h, w = img.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 > x1 and y2 > y1:
                img = img[y1:y2, x1:x2]

        thumb = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise ValueError("Could not create thumbnail from photo.")
        return encoded.tobytes()