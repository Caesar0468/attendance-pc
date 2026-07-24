"""Service for worker management business logic"""
from typing import Any

from fastapi import UploadFile

from app.core.exceptions import (
    FaceDetectionError,
    FileProcessingError,
    InvalidInputException,
    NotFoundException,
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
        worker_repo: WorkerRepository
    ):
        self.storage = storage
        self.face_service = face_service
        self.worker_repo = worker_repo
    
    async def enroll_worker(
        self,
        name: str,
        photos: list[UploadFile],
        min_photos: int,
        max_photos: int
    ) -> dict[str, Any]:
        """Enroll a new worker with photos
        
        Flow:
        1. Validate photo count
        2. Extract embeddings from each photo (FaceService)
        3. Create thumbnail from first photo (StorageService)
        4. Save worker to database (WorkerRepository)
        
        Args:
            name: Worker's name
            photos: List of uploaded photo files
            min_photos: Minimum required photos
            max_photos: Maximum allowed photos
            
        Returns:
            Dict with worker id, name, and thumbnail_path
            
        Raises:
            HTTPException: If validation fails or face detection fails
        """
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
                
                # Extract face embedding
                emb = self.face_service.get_single_embedding(data)
                embeddings.append(emb.tolist())
                
                # Create thumbnail from first photo
                if i == 0:
                    thumb_bytes = self.face_service.create_thumbnail(data)
                    _, thumbnail_path = self.storage.save_worker_thumbnail(thumb_bytes)
        
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
        
        # Save worker to database
        worker_id = self.worker_repo.create(name.strip(), embeddings, thumbnail_path)
        
        return {
            "id": worker_id,
            "name": name.strip(),
            "thumbnail_path": thumbnail_path
        }
    
    def delete_worker_and_thumbnail(self, worker_id: int) -> None:
        """Deletes a worker and their associated thumbnail file.
        
        Args:
            worker_id: ID of the worker to delete.
            
        Raises:
            WorkerNotFoundError: If the worker is not found.
        """
        thumbnail_path = self.worker_repo.delete(worker_id)
        
        if thumbnail_path is None:
            raise WorkerNotFoundError()
        
        if thumbnail_path:
            self.storage.delete_thumbnail(thumbnail_path)
    
    async def update_worker(
        self,
        worker_id: int,
        name: str | None,
        photos: list[UploadFile] | None
    ) -> dict[str, Any]:
        """Update an existing worker's information
        
        Flow:
        1. Fetch existing worker data (WorkerRepository)
        2. If new photos provided, extract embeddings and create new thumbnail
        3. Update worker in database (WorkerRepository)
        4. Clean up old thumbnail if replaced
        
        Args:
            worker_id: ID of worker to update
            name: New name (optional)
            photos: New photos to add (optional)
            
        Returns:
            Dict with worker id, name, and thumbnail_path
            
        Raises:
            HTTPException: If worker not found or face detection fails
        """
        if photos is None:
            photos = []
        
        # Get existing worker
        worker = self.worker_repo.get_by_id(worker_id)
        if not worker:
            raise WorkerNotFoundError()
        
        new_name = name.strip() if name else worker["name"]
        embeddings = parse_embeddings(worker["embeddings"])
        old_thumbnail_path = worker["thumbnail_path"]
        thumbnail_path = old_thumbnail_path
        
        # Process new photos if provided
        if photos:
            try:
                first_data = None
                for photo in photos:
                    if not photo.filename:
                        continue
                    data = await photo.read()
                    if not data:
                        continue
                    
                    # Extract embedding and add to existing list
                    emb = self.face_service.get_single_embedding(data)
                    embeddings.append(emb.tolist())
                    
                    if first_data is None:
                        first_data = data
                
                # Create new thumbnail from first new photo
                if first_data:
                    thumb_bytes = self.face_service.create_thumbnail(first_data)
                    _, thumbnail_path = self.storage.save_worker_thumbnail(thumb_bytes)
            
            except (ValueError, RuntimeError) as e:
                raise FaceDetectionError(detail=f"Face detection or embedding extraction failed: {e}") from e
            except Exception as e:
                raise FileProcessingError(
                    detail="Could not process that photo. Please use clear, well-lit photos."
                ) from e
        
        # Update worker in database
        self.worker_repo.update(worker_id, new_name, embeddings, thumbnail_path)
        
        # Clean up old thumbnail if it was replaced
        if thumbnail_path != old_thumbnail_path and old_thumbnail_path:
            self.storage.delete_thumbnail(old_thumbnail_path)
        
        return {
            "id": worker_id,
            "name": new_name,
            "thumbnail_path": thumbnail_path
        }
