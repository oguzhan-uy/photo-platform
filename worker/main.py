"""RQ worker entrypoint. Same image as the API, started with a different command."""
import logging

from rq import Worker

from app.config import get_settings
from app.logging_config import configure_logging
from app.redis_client import redis_conn, task_queue

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("worker")


def main() -> None:
    log.info("worker starting", extra={"extra_fields": {"queue": settings.queue_name}})
    worker = Worker([task_queue], connection=redis_conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
