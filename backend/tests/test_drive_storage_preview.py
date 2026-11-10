import os
import io
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.models.image import ImageItem
from app.models.category import Category
from app.main import app
from app.services.drive_service import GoogleDriveService
from app.services.drive_worker import DriveSyncWorker

TEST_DB_FILE = "./test_suite.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE}"

@pytest.fixture(scope="module")
def test_db():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass

    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.clear()
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass


def test_image_item_model_fields(test_db):
    db = test_db()
    img = ImageItem(
        uuid="test-uuid-1",
        filename="test.jpg",
        original_filename="orig.jpg",
        file_path="/tmp/test.jpg",
        storage_path="storage/processed/test.jpg",
        file_size=1024,
        width=100,
        height=100,
        format="JPEG",
        sha256="fake_sha256",
        phash="fake_phash",
        status="PENDING",
        drive_status="PENDING",
        drive_retry_count=0,
        drive_next_retry_at=datetime.datetime.utcnow(),
        drive_last_error=None,
        drive_backup_data=b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
    )
    db.add(img)
    db.commit()
    db.refresh(img)

    assert img.id is not None
    assert img.drive_retry_count == 0
    assert img.drive_backup_data == b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
    assert img.drive_status == "PENDING"
    db.close()


def test_drive_service_supports_all_statuses(test_db, monkeypatch):
    db = test_db()

    class FakeFiles:
        def list(self, **kwargs):
            class Req:
                def execute(self):
                    return {"files": []}
            return Req()

        def create(self, **kwargs):
            class Req:
                def execute(self):
                    return {"id": "fake_drive_file_123", "webViewLink": "https://drive.google.com/fake"}
            return Req()

    class FakeDrive:
        def files(self):
            return FakeFiles()

    service = GoogleDriveService(db)
    monkeypatch.setattr(service, "_get_drive_client", lambda: FakeDrive())

    for test_status in ["PENDING", "REVIEW_REQUIRED", "APPROVED", "REJECTED", "DUPLICATE"]:
        img = ImageItem(
            uuid=f"status-uuid-{test_status}",
            filename=f"{test_status}.jpg",
            original_filename=f"{test_status}.jpg",
            file_path=f"storage/test_{test_status}.jpg",
            storage_path=f"storage/processed/{test_status}.jpg",
            file_size=100,
            width=50,
            height=50,
            format="JPEG",
            sha256=f"hash_{test_status}",
            phash=f"phash_{test_status}",
            status=test_status,
            drive_status="PENDING",
            drive_backup_data=b"\xFF\xD8\xFF\xE0fake"
        )
        db.add(img)
        db.commit()
        db.refresh(img)

        # Ensure upload_image_to_drive succeeds for every status
        res = service.upload_image_to_drive(img.id)
        assert res["success"] is True
        db.refresh(img)
        assert img.drive_status == "COMPLETED"
        assert img.drive_file_id == "fake_drive_file_123"
        # Verify backup bytes cleared only after successful Drive upload
        assert img.drive_backup_data is None

    db.close()


def test_prevent_duplicate_drive_upload_using_app_properties(test_db, monkeypatch):
    db = test_db()

    class FakeFilesWithExisting:
        def list(self, q=None, **kwargs):
            class Req:
                def execute(self):
                    # Simulate finding the file via appProperties
                    if "appProperties has" in (q or ""):
                        return {"files": [{"id": "existing_drive_id_999", "webViewLink": "https://drive.google.com/existing"}]}
                    return {"files": []}
            return Req()

        def create(self, **kwargs):
            body = kwargs.get("body", {})
            if body.get("mimeType") == "application/vnd.google-apps.folder":
                class FolderReq:
                    def execute(self):
                        return {"id": "fake_folder_999", "name": body.get("name")}
                return FolderReq()
            pytest.fail("create() should NOT be called for image file if appProperties matched existing file!")

    class FakeDrive:
        def files(self):
            return FakeFilesWithExisting()

    service = GoogleDriveService(db)
    monkeypatch.setattr(service, "_get_drive_client", lambda: FakeDrive())

    img = ImageItem(
        uuid="appprop-uuid",
        filename="appprop.jpg",
        original_filename="appprop.jpg",
        file_path="/tmp/appprop.jpg",
        storage_path="storage/processed/appprop.jpg",
        file_size=100,
        width=50,
        height=50,
        format="JPEG",
        sha256="hash_appprop",
        phash="phash_appprop",
        status="APPROVED",
        drive_status="PENDING",
        drive_backup_data=b"testbytes"
    )
    db.add(img)
    db.commit()
    db.refresh(img)

    res = service.upload_image_to_drive(img.id)
    assert res["success"] is True
    assert res["drive_file_id"] == "existing_drive_id_999"
    db.refresh(img)
    assert img.drive_file_id == "existing_drive_id_999"
    assert img.drive_status == "COMPLETED"
    assert img.drive_backup_data is None
    db.close()


def test_image_file_preview_returns_bytes_not_redirect(test_db, monkeypatch):
    import app.api.v1.endpoints.images as images_endpoint
    # Simulate container filesystem wiped after Render restart (local disk missing)
    monkeypatch.setattr(images_endpoint, "find_physical_image_file", lambda img: None)

    db = test_db()
    # Image with database backup data and guaranteed non-existent local file path
    img = ImageItem(
        uuid="preview-uuid-bytes-unique-99",
        filename="preview_bytes_unique_99.jpg",
        original_filename="preview_bytes_unique_99.jpg",
        file_path="/guaranteed/missing/path/preview_bytes_unique_99.jpg",
        storage_path="storage/processed/preview_bytes_unique_99.jpg",
        file_size=12,
        width=10,
        height=10,
        format="JPEG",
        sha256="sha_prev_unique",
        phash="phash_prev_unique",
        status="REVIEW_REQUIRED",
        drive_status="PENDING",
        drive_backup_data=b"\xFF\xD8\xFF\xE0\x00\x10JFIFfakebytes"
    )
    db.add(img)
    db.commit()
    img_id = img.id
    db.close()

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/images/{img_id}/file", follow_redirects=False)
        # MUST return 200 with raw image bytes, NOT 307 redirect
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.headers.get("X-Image-Source") == "database-backup"
        assert resp.content == b"\xFF\xD8\xFF\xE0\x00\x10JFIFfakebytes"


def test_image_file_preview_fetches_private_drive_bytes(test_db, monkeypatch):
    import app.api.v1.endpoints.images as images_endpoint
    monkeypatch.setattr(images_endpoint, "find_physical_image_file", lambda img: None)

    db = test_db()
    img = ImageItem(
        uuid="preview-drive-fetch-unique-99",
        filename="drive_fetch_unique_99.png",
        original_filename="drive_fetch_unique_99.png",
        file_path="/guaranteed/missing/drive_fetch_unique_99.png",
        storage_path="storage/processed/drive_fetch_unique_99.png",
        file_size=8,
        width=10,
        height=10,
        format="PNG",
        sha256="sha_df_unique",
        phash="phash_df_unique",
        status="APPROVED",
        drive_status="COMPLETED",
        drive_file_id="drive_stream_123",
        drive_backup_data=None  # No local backup data, must fetch from Drive API
    )
    db.add(img)
    db.commit()
    img_id = img.id
    db.close()

    # Monkeypatch download_image_bytes
    monkeypatch.setattr(
        GoogleDriveService,
        "download_image_bytes",
        lambda self, file_id: (b"\x89PNG\r\n\x1a\nfake_streamed_png", "image/png")
    )

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/images/{img_id}/file", follow_redirects=False)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.headers.get("X-Image-Source") == "google-drive-authenticated"
        assert resp.content == b"\x89PNG\r\n\x1a\nfake_streamed_png"


def test_drive_worker_backoff_and_recovery(test_db, monkeypatch):
    worker = DriveSyncWorker(poll_interval=1)
    db = test_db()

    interrupted = ImageItem(
        uuid="interrupted-uuid",
        filename="interrupted.jpg",
        original_filename="interrupted.jpg",
        file_path="/tmp/interrupted.jpg",
        storage_path="storage/processed/interrupted.jpg",
        file_size=10,
        width=10,
        height=10,
        format="JPEG",
        sha256="hash_int",
        phash="phash_int",
        status="APPROVED",
        drive_status="UPLOADING",  # Interrupted state
        drive_backup_data=b"test"
    )
    db.add(interrupted)
    db.commit()
    target_id = interrupted.id
    db.close()

    monkeypatch.setattr("app.services.drive_worker.SessionLocal", test_db)
    worker._recover_interrupted_uploads()

    db_check = test_db()
    recovered = db_check.query(ImageItem).filter(ImageItem.id == target_id).first()
    assert recovered.drive_status == "PENDING"
    db_check.close()
