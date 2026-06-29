"""Shared Redis connection and the RQ queue used by API and worker alike."""
from redis import Redis
from rq import Queue

from app.config import get_settings

settings = get_settings()

redis_conn = Redis.from_url(settings.redis_url)
task_queue = Queue(settings.queue_name, connection=redis_conn)
