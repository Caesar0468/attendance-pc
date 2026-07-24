"""Service for attendance processing business logic"""
from datetime import date as date_type
from typing import Any

from app.config import load_config
from app.core.exceptions import (
    ConfigurationError,
    FaceDetectionError,
    FileProcessingError,
    InvalidInputException,
    UncertainMatchNotFoundError,
    WorkerNotFoundError,
)
from app.face_service import FaceService
from app.matching import match_face
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas import ConfirmUncertainRequest
from app.services.storage_service import StorageService
from app.ws_manager import WebSocketManager

class AttendanceService:
    """Handles business logic for attendance photo processing and management."""

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

    async def process_attendance_photo(
        self,
        image_bytes: bytes,
        username: str,
        session: str,
        timestamp: str,
        photo_date: str,
    ) -> dict[str, Any]:
        """Process an uploaded attendance photo.

        Flow:
        1. Validate session
        2. Save photo with EXIF (StorageService)
        3. Log photo to database (AttendanceRepository)
        4. Detect faces (FaceService)
        5. Match faces against workers (WorkerRepository + matching logic)
        6. Mark present or create uncertain matches (AttendanceRepository)
        7. Broadcast updates via WebSocket

        Args:
            image_bytes: Raw image data
            username: Uploader's username
            session: 'morning' or 'evening' (already normalized)
            timestamp: ISO timestamp string
            photo_date: Date string (YYYY-MM-DD)

        Returns:
            Dict with saved status, filename, faces detected, matched/uncertain lists, and today's data
        """
        config = load_config()
        try:
            sim_threshold = float(config["similarity_threshold"])
            uncertain_threshold = float(config["uncertain_threshold"])
        except (KeyError, ValueError) as e:
            raise ConfigurationError(
                detail=f"Missing or invalid similarity/uncertainty threshold in config: {e}"
            ) from e

        # Normalize session
        session = session.lower().strip()
        if session not in ("morning", "evening"):
            raise InvalidInputException(detail="Session must be 'morning' or 'evening'.")

        # Save photo with EXIF data
        save_path, relative_filename = self.storage.save_attendance_photo(
            image_bytes, username, photo_date, timestamp, session
        )

        # Parse time for database logging
        try:
            dt = self.storage._datetime_from_timestamp(timestamp)
            time_str = dt.strftime("%H%M%S")
        except Exception:
            time_str = "000000"

        # Log photo to database
        self.attendance_repo.log_photo(
            relative_filename, username, photo_date, time_str, session
        )

        # Detect faces in the photo
        try:
            faces = self.face_service.detect_faces(image_bytes)
        except (ValueError, RuntimeError) as e:
            raise FaceDetectionError(detail=f"Face detection failed: {e}") from e
        except Exception as e:
            raise FileProcessingError(detail="Could not read that photo, please try again.") from e

        if not faces:
            return {
                "saved": True,
                "filename": save_path.name,
                "faces_detected": 0,
                "matched": [],
                "uncertain": [],
                "message": "Photo saved but no faces were detected.",
            }

        # Get all workers with embeddings for matching
        worker_embeddings = self.worker_repo.get_all_with_embeddings()

        matched_workers: list[int] = []
        uncertain_items: list[int] = []

        # Process each detected face
        for face in faces:
            status, worker_id, score = match_face(
                face.embedding,
                worker_embeddings,
                sim_threshold,
                uncertain_threshold,
            )

            if status == "matched" and worker_id is not None:
                self.attendance_repo.mark_present(
                    worker_id, photo_date, session, confirmed_by="auto"
                )
                if worker_id not in matched_workers:
                    matched_workers.append(worker_id)

            elif status == "uncertain":
                # Save face crop
                _, crop_rel_path = self.storage.save_uncertain_crop(face.crop_bytes)

                # Create uncertain match record
                uncertain_id = self.attendance_repo.create_uncertain_match(
                    photo_date, session, crop_rel_path, worker_id, score
                )
                uncertain_items.append(uncertain_id)

        # Get updated today's data
        today_data = self.attendance_repo.get_today_attendance(photo_date)

        # Broadcast update via WebSocket
        await self.ws_manager.broadcast(
            {"type": "attendance_update", "data": today_data}
        )

        return {
            "saved": True,
            "filename": save_path.name,
            "faces_detected": len(faces),
            "matched": matched_workers,
            "uncertain": uncertain_items,
            "today": today_data,
        }

    def get_today_attendance_summary(self, day: str | None = None) -> dict[str, Any]:
        """Get today's attendance summary.
        
        Args:
            day: Date string (YYYY-MM-DD). Defaults to today.
            
        Returns:
            Dictionary with today's attendance data.
            
        Raises:
            InvalidInputException: If the date format is invalid.
        """
        attendance_date = day or date_type.today().isoformat()

        try:
            date_type.fromisoformat(attendance_date)
        except ValueError as e:
            raise InvalidInputException(detail="Invalid date format.") from e

        return self.attendance_repo.get_today_attendance(attendance_date)

    async def confirm_or_discard_uncertain_match(
        self, body: ConfirmUncertainRequest
    ) -> dict[str, Any]:
        """Confirms or discards an uncertain attendance match.
        
        Args:
            body: Request body with uncertain_id and optional worker_id.
            
        Returns:
            Dictionary with success status and updated today's attendance data.
            
        Raises:
            UncertainMatchNotFoundError: If the uncertain match is not found.
            WorkerNotFoundError: If the worker_id provided for confirmation is not found.
        """
        uncertain_match = self.attendance_repo.get_uncertain_by_id(body.uncertain_id)
        if not uncertain_match:
            raise UncertainMatchNotFoundError()

        if body.worker_id is None:
            self.attendance_repo.discard_uncertain(body.uncertain_id)
        else:
            if not self.worker_repo.exists(body.worker_id):
                raise WorkerNotFoundError()

            self.attendance_repo.confirm_uncertain(body.uncertain_id, body.worker_id)
            self.attendance_repo.mark_present(
                body.worker_id,
                uncertain_match["date"],
                uncertain_match["session"],
                confirmed_by="manual",
            )

        data = self.attendance_repo.get_today_attendance()
        await self.ws_manager.broadcast({"type": "attendance_update", "data": data})
        return {"success": True, "today": data}
