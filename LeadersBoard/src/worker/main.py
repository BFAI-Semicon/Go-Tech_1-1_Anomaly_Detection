"""LeadersBoard Worker - Main entry point."""

import logging
import os
import signal
import sys
from pathlib import Path

from redis import Redis

from src.adapters.filesystem_storage_adapter import FileSystemStorageAdapter
from src.adapters.redis_job_queue_adapter import RedisJobQueueAdapter
from src.adapters.redis_job_status_adapter import RedisJobStatusAdapter
from src.worker.job_worker import JobWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def _create_worker() -> JobWorker:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_client = Redis.from_url(redis_url)
    queue = RedisJobQueueAdapter(redis_client)
    status = RedisJobStatusAdapter(redis_client)
    storage_root = Path(os.getenv("UPLOAD_ROOT", "/shared/submissions"))
    storage = FileSystemStorageAdapter(storage_root)
    return JobWorker(queue=queue, status=status, storage=storage)


def main() -> None:
    worker = _create_worker()
    signal.signal(signal.SIGTERM, lambda sig, frame: worker.stop())
    signal.signal(signal.SIGINT, lambda sig, frame: worker.stop())
    try:
        worker.run()
    finally:
        logger.info("Worker shutdown complete.")


if __name__ == "__main__":
    main()
