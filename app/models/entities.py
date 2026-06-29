"""Domain entities: Client, Gallery, Photo, Face, JobAudit.

Column types are kept portable (Uuid, Enum, etc.) so the test suite can run
on SQLite. The embedding column falls back to Text on SQLite (tests never store
real embeddings — they mock insightface at the job boundary).
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.types import EMBEDDING_TYPE


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PhotoStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Client(Base):
    __tablename__ = "client"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(200))
    contact: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Biometric consent is OFF until explicitly granted (milestone 5 enforces it).
    consent_biometric: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_biometric_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    galleries: Mapped[list["Gallery"]] = relationship(back_populates="client")


class Gallery(Base):
    __tablename__ = "gallery"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    # Per-gallery passcode is stored hashed (bcrypt), never in plaintext.
    passcode_hash: Mapped[str] = mapped_column(String(200))
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Photographer-chosen cover photo shown blurred on the public landing page.
    cover_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("photo.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="galleries")
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="gallery",
        primaryjoin="Photo.gallery_id == Gallery.id",
        foreign_keys="[Photo.gallery_id]",
    )

    def is_accessible(self, now: datetime | None = None) -> bool:
        now = now or _now()
        if not self.published:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True


class Photo(Base):
    __tablename__ = "photo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    gallery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gallery.id", ondelete="CASCADE"))
    # R2 object keys; null until the upload (milestone 3) completes.
    r2_key_original: Mapped[str | None] = mapped_column(String(500), nullable=True)
    r2_key_web: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Content hash powers idempotent ingest (milestone 3).
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[PhotoStatus] = mapped_column(
        Enum(PhotoStatus, name="photo_status"), default=PhotoStatus.uploaded
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    gallery: Mapped["Gallery"] = relationship(
        back_populates="photos",
        primaryjoin="Photo.gallery_id == Gallery.id",
        foreign_keys="[Photo.gallery_id]",
    )
    faces: Mapped[list["Face"]] = relationship(back_populates="photo", cascade="all, delete-orphan")


class Face(Base):
    """One row per detected face region in a photo.

    gallery_id is denormalized here so gallery-scoped vector queries (pgvector
    nearest-neighbour search) never need to join through photo → gallery.
    Biometric consent is enforced upstream: this table is only populated when
    client.consent_biometric is True at the time the embed job runs.
    """
    __tablename__ = "face"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    photo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("photo.id", ondelete="CASCADE"), index=True
    )
    # Denormalized for scoped pgvector queries without a join.
    gallery_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    # Bounding box in pixels (top-left x, y; width, height).
    bbox_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # InsightFace detection confidence (0–1).
    det_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ArcFace 512-d embedding; Vector(512) on Postgres, Text on SQLite (tests).
    embedding: Mapped[Any] = mapped_column(EMBEDDING_TYPE, nullable=True)
    # HDBSCAN cluster label (-1 = noise / unclustered).
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    photo: Mapped["Photo"] = relationship(back_populates="faces")


class JobAudit(Base):
    """One row per job execution outcome — makes silent failures impossible to hide."""
    __tablename__ = "job_audit"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(20))   # "success" | "failed"
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, server_default=func.now()
    )


class DeletionLog(Base):
    """Immutable audit record for every compliance-driven hard-deletion.

    Written on: client hard-delete (GDPR erasure), gallery expiry, biometric
    consent revocation. Provides a verifiable receipt of what was purged and when.
    """
    __tablename__ = "deletion_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # "client_delete" | "gallery_expire" | "consent_revoke"
    event_type: Mapped[str] = mapped_column(String(50))
    # "client" | "gallery"
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    purged_photos: Mapped[int] = mapped_column(Integer, default=0)
    purged_faces: Mapped[int] = mapped_column(Integer, default=0)
    purged_r2_objects: Mapped[int] = mapped_column(Integer, default=0)
    # "admin" | "expiry_worker"
    executed_by: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
