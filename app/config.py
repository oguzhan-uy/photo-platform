"""Application configuration, loaded from environment variables (12-factor)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"

    # Postgres (psycopg3). Sync on purpose: API-side DB calls are fast metadata
    # reads; heavy work is offloaded to the worker.
    database_url: str = "postgresql+psycopg://photo:photo@postgres:5432/photo"

    # Redis / RQ
    redis_url: str = "redis://redis:6379/0"
    queue_name: str = "default"

    # Auth
    admin_token: str = "dev-admin-token-change-me"      # photographer (admin) bearer token
    secret_key: str = "dev-secret-change-me"            # signs client gallery tokens
    client_token_ttl_minutes: int = 120

    # Cloudflare R2 (S3-compatible). All values required in production.
    r2_endpoint_url: str = ""           # https://<account-id>.r2.cloudflarestorage.com
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    # If set, presigned URLs have their origin rewritten to this value before being
    # returned to clients. Use for local dev when the S3 endpoint is a Docker-internal
    # hostname (e.g. http://minio:9000) but browsers need http://localhost:9000.
    r2_public_url: str = ""

    # Short-lived delivery URL lifetime for clients (presigned GET).
    presigned_get_ttl: int = 300        # 5 min

    # Face pipeline (M5)
    # InsightFace model name; buffalo_l gives ArcFace 512-d embeddings, CPU/ARM-friendly.
    face_model: str = "buffalo_l"
    # Directory where InsightFace downloads and caches model files (~300 MB).
    face_model_cache_dir: str = "/models"
    # Cosine distance threshold for face search (0 = identical, 2 = opposite).
    # For L2-normalised ArcFace embeddings: distance 0.5 = cosine similarity 0.5.
    # Tune down (e.g. 0.35) for stricter matching, up for more recall.
    face_cosine_threshold: float = 0.5
    # Maximum photos returned by a single face search query.
    face_search_top_k: int = 20
    # HDBSCAN minimum cluster size; smaller values create more clusters.
    face_min_cluster_size: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
