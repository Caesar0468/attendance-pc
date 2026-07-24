"""Service for worker management business logic"""
from typing import Any

from fastapi import UploadFile

from app.config import load_config
from app.core.exceptions import (
    BaseAppException,
    FaceDetectionError,
    FileProcessingError,
    InvalidInputException,
    WorkerNotFoundError,
)
from app.database import parse_embeddings
from app.face_service import FaceService
from app.repositories.worker_repository import WorkerRepository
from app.services.storage_service import StorageService


class WorkerService:
    """Handles business logic for worker enrollment and management"""

    def __init__(
        self,
        storage: StorageService,
        face_service: FaceService,
        worker_repo: WorkerRepository,
    ):
        self.storage = storage
        self.face_service = face_service
        self.worker_repo = worker_repo

    async def enroll_worker(
        self,
        name: str,
        photos: list[UploadFile],
        min_photos: int,
        max_photos: int,
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise InvalidInputException(detail="Worker name cannot be empty.")

        if len(photos) < min_photos:
            raise InvalidInputException(
                detail=f"Please provide at least {min_photos} photos for reliable recognition.",
            )
        if len(photos) > max_photos:
            raise InvalidInputException(
                detail=f"Please provide no more than {max_photos} photos per worker.",
            )

        embeddings: list[list[float]] = []
        thumbnail_path = None

        try:
            for i, photo in enumerate(photos):
                data = await photo.read()
                if not data:
                    raise FileProcessingError(detail="One of the photos was empty. Please try again.")

                emb = self.face_service.get_single_embedding(data)
                embeddings.append(emb.tolist())

                if i == 0:
                    thumb_bytes = self.face_service.create_thumbnail(data)
                    _, thumbnail_path = self.storage.save_worker_thumbnail(thumb_bytes)

        except BaseAppException:
            if thumbnail_path:
                self.storage.delete_thumbnail(thumbnail_path)
            raise

        except (ValueError, RuntimeError) as e:
            if thumbnail_path:
                self.storage.delete_thumbnail(thumbnail_path)
            raise FaceDetectionError(detail=f"Face detection or embedding extraction failed: {e}") from e

        except Exception as e:
            if thumbnail_path:
                self.storage.delete_thumbnail(thumbnail_path)
            raise FileProcessingError(
                detail="Could not process that photo. Please use clear, well-lit photos."
            ) from e

        worker_id = self.worker_repo.create(clean_name, embeddings, thumbnail_path)

        return {
            "id": worker_id,
            "name": clean_name,
            "thumbnail_path": thumbnail_path,
        }

    def delete_worker_and_thumbnail(self, worker_id: int) -> None:
        found, thumbnail_path = self.worker_repo.delete(worker_id)

        if not found:
            raise WorkerNotFoundError()

        if thumbnail_path:
            self.storage.delete_thumbnail(thumbnail_path)

    async def update_worker(
        self,
        worker_id: int,
        name: str | None,
        photos: list[UploadFile] | None,
    ) -> dict[str, Any]:
        if photos is None:
            photos = []

        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            raise WorkerNotFoundError()

        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise InvalidInputException(detail="Worker name cannot be empty.")
            new_name = clean_name
        else:
            new_name = worker["name"]

        embeddings = parse_embeddings(worker["embeddings"])
        old_thumbnail_path = worker["thumbnail_path"]
        thumbnail_path = old_thumbnail_path

        if photos:
            config = load_config()
            max_photos = config["photos_per_worker_max"]
            valid_photos = [p for p in photos if p.filename]

            if len(valid_photos) > max_photos:
                raise InvalidInputException(
                    detail=f"Please upload no more than {max_photos} photos at a time."
                )

            try:
                first_data = None
                for photo in valid_photos:
                    data = await photo.read()
                    if not data:
                        continue

                    emb = self.face_service.get_single_embedding(data)
                    embeddings.append(emb.tolist())

                    if first_data is None:
                        first_data = data

                if first_data:
                    thumb_bytes = self.face_service.create_thumbnail(first_data)
                    _, thumbnail_path = self.storage.save_worker_thumbnail(thumb_bytes)

            except BaseAppException:
                raise
            except (ValueError, RuntimeError) as e:
                raise FaceDetectionError(detail=f"Face detection or embedding extraction failed: {e}") from e
            except Exception as e:
                raise FileProcessingError(
                    detail="Could not process that photo. Please use clear, well-lit photos."
                ) from e

        self.worker_repo.update(worker_id, new_name, embeddings, thumbnail_path)

        if thumbnail_path != old_thumbnail_path and old_thumbnail_path:
            self.storage.delete_thumbnail(old_thumbnail_path)

        return {
            "id": worker_id,
            "name": new_name,
            "thumbnail_path": thumbnail_path,
        }