"""Pydantic request/response models. Note: passcodes and R2 keys are never returned."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PhotoStatus


class ClientCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    contact: str | None = Field(default=None, max_length=320)


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    display_name: str
    contact: str | None
    consent_biometric: bool
    created_at: datetime


class GalleryCreate(BaseModel):
    client_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    passcode: str = Field(min_length=4, max_length=72)
    published: bool = True
    expires_at: datetime | None = None


class GalleryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    published: bool
    expires_at: datetime | None
    cover_photo_id: uuid.UUID | None
    created_at: datetime


class PublicGalleryOut(BaseModel):
    """Minimal gallery info returned to unauthenticated visitors on the landing page."""
    id: uuid.UUID
    title: str
    has_cover: bool


class SetCoverIn(BaseModel):
    photo_id: uuid.UUID


class GalleryAccessRequest(BaseModel):
    passcode: str = Field(min_length=1, max_length=72)


class GalleryAccessResponse(BaseModel):
    token: str
    gallery_id: uuid.UUID
    expires_in: int  # seconds


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    gallery_id: uuid.UUID
    status: PhotoStatus
    width: int | None
    height: int | None
    created_at: datetime


class PhotoConfirmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    photo_id: uuid.UUID
    status: PhotoStatus
    job_id: str


class PhotoURLOut(BaseModel):
    url: str        # short-lived presigned GET URL
    expires_in: int # seconds


# ---- Milestone 5: face pipeline ----

class ConsentUpdate(BaseModel):
    consent_biometric: bool


class FaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    photo_id: uuid.UUID
    gallery_id: uuid.UUID
    bbox_x: int | None
    bbox_y: int | None
    bbox_w: int | None
    bbox_h: int | None
    det_score: float | None
    cluster_id: int | None
    created_at: datetime


class ClusterOut(BaseModel):
    """One entry per distinct HDBSCAN cluster in a gallery (excludes noise, cluster_id=-1)."""
    cluster_id: int
    face_count: int
    representative_photo_id: uuid.UUID  # photo_id of the first face in this cluster


class FaceSearchResult(BaseModel):
    """Single result from a face similarity search."""
    photo_id: uuid.UUID
    distance: float  # cosine distance (0 = identical, 2 = opposite)


# ---- Milestone 6: compliance ----

class DeletionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_type: str
    target_type: str
    target_id: uuid.UUID
    purged_photos: int
    purged_faces: int
    purged_r2_objects: int
    executed_by: str
    created_at: datetime


class ClientDeleteOut(BaseModel):
    """Deletion receipt returned after a GDPR erasure request."""
    client_id: uuid.UUID
    purged_galleries: int
    purged_photos: int
    purged_faces: int
    purged_r2_objects: int
