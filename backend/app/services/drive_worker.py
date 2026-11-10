import os
import time
import logging
import threading
import datetime
from typing import Optional

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.image import ImageItem
from app.services.drive_service import GoogleDriveService

logger = logging.getLogger("eventdhara.drive_worker")

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 15
MAX_BACKOFF_SECONDS = 3600
BATCH_SIZE = 5
DEFAULT_POLL_INTERVAL_SECONDS = 10


class DriveSyncWorker:
    def __init__(self, poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS):
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the background worker thread and recovers interrupted uploads."""
        if self._thread and self._thread.is_alive():
            logger.info("Drive sync worker is already running.")
            return

        self._stop_event.clear()
        self._wake_event.clear()

        # Recover interrupted uploads from previous container execution
        self._recover_interrupted_uploads()

        self._thread = threading.Thread(
            target=self._run_loop,
            name="DriveSyncWorkerThread",
            daemon=True
        )
        self._thread.start()
        logger.info("Drive background sync worker started.")

    def stop(self, timeout: float = 5.0):
        """Signals the worker to terminate gracefully."""
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            logger.info("Drive background sync worker stopped.")

    def trigger(self):
        """Wakes up the worker immediately when new images are ingested."""
        self._wake_event.set()

    def _recover_interrupted_uploads(self):
        """
        Recovers images left in UPLOADING state caused by sudden server/Render restarts.
        Resets them to PENDING so they are immediately queued for upload.
        """
        try:
            with SessionLocal() as db:
                interrupted = (
                    db.query(ImageItem)
                    .filter(ImageItem.drive_status == "UPLOADING")
                    .all()
                )
                if interrupted:
                    count = len(interrupted)
                    for img in interrupted:
                        img.drive_status = "PENDING"
                        img.drive_next_retry_at = datetime.datetime.utcnow()
                    db.commit()
                    logger.info("Recovered %d interrupted Drive upload(s) after restart.", count)
        except Exception as e:
            logger.warning("Error recovering interrupted Drive uploads on startup: %s", e)

    def _run_loop(self):
        """Main polling and synchronization loop."""
        logger.info("Drive background worker loop initiated.")
        while not self._stop_event.is_set():
            try:
                processed_any = self._process_pending_batch()
            except Exception as e:
                logger.error("Unexpected error in Drive sync worker cycle: %s", e)
                processed_any = False

            # If images were processed, check immediately if more are waiting; otherwise wait for interval or trigger
            wait_time = 0.5 if processed_any else self.poll_interval
            self._wake_event.wait(timeout=wait_time)
            self._wake_event.clear()

        logger.info("Drive background worker loop exiting.")

    def _process_pending_batch(self) -> bool:
        """
        Polls PostgreSQL for pending/failed uploads using safe row locking,
        executes Drive uploads, handles exponential backoff on failure,
        and reconstructs missing local files from DB backup.
        Returns True if any items were processed.
        """
        now = datetime.datetime.utcnow()
        with SessionLocal() as db:
            try:
                # Safe row locking with PostgreSQL (skip_locked prevents worker collision across instances)
                query = (
                    db.query(ImageItem)
                    .filter(
                        ImageItem.drive_status.in_(["PENDING", "FAILED"]),
                        (ImageItem.drive_next_retry_at.is_(None)) | (ImageItem.drive_next_retry_at <= now),
                        ImageItem.drive_retry_count < MAX_RETRIES
                    )
                    .order_by(ImageItem.id.asc())
                )

                if db.bind and db.bind.dialect.name == "postgresql":
                    query = query.with_for_update(skip_locked=True)

                candidates = query.limit(BATCH_SIZE).all()
                if not candidates:
                    return False

                candidate_ids = [c.id for c in candidates]
                logger.info("Processing %d pending Drive upload candidate(s): %s", len(candidate_ids), candidate_ids)

            except Exception as q_err:
                logger.error("Error querying Drive pending upload candidates: %s", q_err)
                return False

            # Process candidates within this session
            service = GoogleDriveService(db)
            for item in candidates:
                if self._stop_event.is_set():
                    break

                try:
                    res = service.upload_image_to_drive(item.id)
                    if res.get("success"):
                        logger.info("Successfully synced image #%s ('%s') to Google Drive.", item.id, item.original_filename)
                    else:
                        # Upload failed: apply exponential backoff
                        current_retries = (item.drive_retry_count or 0) + 1
                        delay = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** (current_retries - 1)))
                        item.drive_retry_count = current_retries
                        item.drive_next_retry_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)
                        item.drive_status = "FAILED"
                        item.drive_last_error = (res.get("message") or "Unknown upload error")[:1000]
                        db.commit()
                        logger.warning(
                            "Drive upload failed for image #%s (attempt %d/%d). Next retry in %ds: %s",
                            item.id, current_retries, MAX_RETRIES, delay, item.drive_last_error
                        )
                except Exception as sync_err:
                    current_retries = (item.drive_retry_count or 0) + 1
                    delay = min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** (current_retries - 1)))
                    item.drive_retry_count = current_retries
                    item.drive_next_retry_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)
                    item.drive_status = "FAILED"
                    item.drive_last_error = str(sync_err)[:1000]
                    db.commit()
                    logger.error("Exception uploading image #%s to Drive: %s", item.id, sync_err)

            return True


# Global singleton instance
_global_worker: Optional[DriveSyncWorker] = None


def get_drive_worker() -> DriveSyncWorker:
    global _global_worker
    if _global_worker is None:
        _global_worker = DriveSyncWorker()
    return _global_worker


def start_drive_worker():
    worker = get_drive_worker()
    worker.start()


def stop_drive_worker():
    global _global_worker
    if _global_worker:
        _global_worker.stop()


def trigger_drive_sync():
    global _global_worker
    if _global_worker:
        _global_worker.trigger()
