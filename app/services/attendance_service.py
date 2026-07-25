# app/services/attendance_service.py
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import load_config, DEFAULT_CONFIG
from app.core.exceptions import FileProcessingError, InvalidInputException
from app.face_service import FaceService
from app.matching import match_face
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.storage_service import StorageService
from app.ws_manager import WebSocketManager

logger = logging.getLogger(__name__)

# BUGFIX (defense in depth): photos_log.uploader_username is later rendered
# back into the dashboard (Photo Log lightbox). It used to be stored
# completely unsanitized, straight from the upload form field. Combined
# with a frontend escaping gap (now also fixed in static/index.html), an
# attacker-controlled username could execute JS in a logged-in root's
# session. Stripping to a safe charset here means the stored value can
# never carry an HTML/JS-breaking character in the first place, regardless
# of what the frontend does with it later.
_UNSAFE_CHARS = re.compile(r"[^\w\s\-.@]", re.UNICODE)


def _sanitize_display_name(raw: str, max_len: int = 50) -> str:
    cleaned = _UNSAFE_CHARS.sub("", raw or "").strip()
    return cleaned[:max_len] or "unknown"


class AttendanceService:
    def __init__(
        self,
        storage: StorageService,
        face_service: FaceService,
        attendance_repo: AttendanceRepository,
        worker_repo: WorkerRepository,
        ws_manager: WebSocketManager,
    ):
        self.storage = storage
        self.face_service = face_service
        self.attendance_repo = attendance_repo
        self.worker_repo = worker_repo
        self.ws_manager = ws_manager

    def get_today_attendance_summary(self, day: str | None = None) -> dict[str, Any]:
        return self.attendance_repo.get_today_attendance(day)

    async def process_attendance_photo(
        self,
        image_bytes: bytes,
        username: str,
        session: str,
        timestamp: str,
        photo_date: str,
        batch_id: str | None = None
    ) -> dict[str, Any]:

        config = load_config()
        sim_threshold = float(config.get("similarity_threshold", DEFAULT_CONFIG["similarity_threshold"]))
        uncertain_threshold = float(config.get("uncertain_threshold", DEFAULT_CONFIG["uncertain_threshold"]))

        session = session.lower().strip()
        if session not in ("morning", "evening"):
            raise InvalidInputException(detail="Session must be 'morning' or 'evening'.")

        username = _sanitize_display_name(username)

        try:
            faces = self.face_service.detect_faces(image_bytes)
        except Exception as e:
            raise FileProcessingError(detail=f"Could not process photo: {e}")

        if not faces:
            today_data = self.attendance_repo.get_today_attendance(photo_date)
            return {
                "saved": False,
                "filename": "none",
                "faces_detected": 0,
                "matched": [],
                "uncertain": [],
                "today": today_data,
                "message": "Photo rejected: No faces were detected."
            }

        # BUGFIX: save_attendance_photo now returns the bare filename
        # (save_path.name) instead of a path already containing
        # "photos/<date>/<session>/", which used to get duplicated by
        # gallery.py / report_generator.py. See storage_service.py.
        save_path, filename = self.storage.save_attendance_photo(
            image_bytes, username, photo_date, timestamp, session
        )

        dt = self.storage._datetime_from_timestamp(timestamp)
        time_str = dt.strftime("%H%M%S")

        photo_log_id = self.attendance_repo.log_photo(
            filename, username, photo_date, time_str, session, batch_id
        )

        worker_embeddings = self.worker_repo.get_all_with_embeddings()

        classified = []
        for face in faces:
            status, worker_id, score = match_face(
                face.embedding, worker_embeddings, sim_threshold, uncertain_threshold
            )
            classified.append((face, status, worker_id, score))

        # A worker cannot physically appear twice in one photo. If the same
        # worker_id matched more than one face here, that's a bad crop or a
        # lookalike — route ALL of that worker's candidate faces to manual
        # review instead of auto-confirming any of them.
        counts: dict[int, int] = {}
        for _, status, worker_id, _ in classified:
            if status == "matched" and worker_id is not None:
                counts[worker_id] = counts.get(worker_id, 0) + 1
        duplicate_ids = {wid for wid, c in counts.items() if c > 1}

        matched_workers = []
        uncertain_items = []

        for face, status, worker_id, score in classified:
            is_dup = status == "matched" and worker_id in duplicate_ids

            if status == "matched" and worker_id is not None and not is_dup:
                self.attendance_repo.mark_present(worker_id, photo_date, session, confirmed_by="auto")
                self.attendance_repo.record_matched_face(
                    worker_id, photo_date, session, photo_log_id, face.bbox, score
                )
                if worker_id not in matched_workers:
                    matched_workers.append(worker_id)
            else:
                emb_list = face.embedding.tolist()
                if batch_id and self.attendance_repo.is_duplicate_uncertain_in_batch(batch_id, emb_list):
                    continue
                _, crop_rel_path = self.storage.save_uncertain_crop(face.crop_bytes)
                uncertain_id = self.attendance_repo.create_uncertain_match(
                    date=photo_date,
                    session=session,
                    face_crop_path=crop_rel_path,
                    suggested_worker_id=worker_id if (status == "uncertain" or is_dup) else None,
                    similarity=score if (status == "uncertain" or is_dup) else None,
                    batch_id=batch_id,
                    embedding=json.dumps(emb_list),
                    photo_log_id=photo_log_id,
                    bbox=face.bbox,
                )
                uncertain_items.append(uncertain_id)

        today_data = self.attendance_repo.get_today_attendance(photo_date)
        await self.ws_manager.broadcast({"type": "attendance_update", "data": today_data})

        return {
            "saved": True,
            "filename": save_path.name,
            "faces_detected": len(faces),
            "matched": matched_workers,
            "uncertain": uncertain_items,
            "today": today_data,
        }

    async def confirm_or_discard_uncertain_match(
        self, match_id: int, confirm: bool, worker_id: int | None
    ) -> dict[str, Any]:
        row = self.attendance_repo.get_uncertain_match(match_id)

        if not row:
            raise InvalidInputException(detail="Match record not found.")
        if row["status"] != "pending":
            raise InvalidInputException(detail="Match record already processed.")

        date_str = row["date"]
        session = row["session"]

        if confirm:
            if worker_id is None:
                raise InvalidInputException(detail="Worker ID is required to confirm a match.")
            self.attendance_repo.mark_present(worker_id, date_str, session, confirmed_by="manual")

            # BUGFIX: manually-confirmed uncertain matches never got a row in
            # attendance_faces, so the Excel report's photo-evidence lookup
            # silently skipped them. Link the crop's original photo/bbox now
            # (requires the uncertain_matches.photo_log_id/bbox columns added
            # in the app/database.py migration).
            photo_log_id = row.get("photo_log_id")
            bbox_json = row.get("bbox")
            if photo_log_id and bbox_json:
                try:
                    bbox = json.loads(bbox_json)
                    self.attendance_repo.record_matched_face(
                        worker_id, date_str, session, photo_log_id, bbox, row.get("similarity") or 0.0
                    )
                except (TypeError, ValueError, json.JSONDecodeError):
                    logger.warning("Could not link photo evidence for match %s", match_id)

            new_status = "confirmed"
        else:
            new_status = "discarded"
            worker_id = None

        self.attendance_repo.update_uncertain_match_status(match_id, new_status, worker_id)

        today_data = self.attendance_repo.get_today_attendance(date_str)
        await self.ws_manager.broadcast({"type": "attendance_update", "data": today_data})
        return {"success": True, "status": new_status, "today": today_data}