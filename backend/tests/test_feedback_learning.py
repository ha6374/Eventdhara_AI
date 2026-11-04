import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.feedback import RejectionFeedback, CategoryFeedbackInsight
from app.services.feedback_service import FeedbackLearningService

client = TestClient(app)


def test_rejection_feedback_collection_and_learning_loop():
    # 1. Upload a test image
    img = Image.new("RGB", (900, 700), color=(180, 200, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    res = client.post(
        "/api/v1/uploads/images",
        files={"files": ("feedback_test_setup.jpg", buf.getvalue(), "image/jpeg")}
    )
    assert res.status_code == 200
    img_id = res.json()["processed_items"][0]["id"]

    # 2. Reject image with feedback
    reject_res = client.post(
        f"/api/v1/images/{img_id}/reject",
        json={
            "rejection_reason": "Wrong Category",
            "custom_feedback": "Photo contains birthday balloons but was uploaded as wedding decor"
        }
    )
    assert reject_res.status_code == 200
    data = reject_res.json()
    assert data["status"] == "REJECTED"
    assert data["rejection_reason"] == "Wrong Category"

    # 3. Verify feedback saved in database
    db = SessionLocal()
    fb = db.query(RejectionFeedback).filter(RejectionFeedback.image_id == img_id).first()
    assert fb is not None
    assert fb.rejection_reason == "Wrong Category"
    assert "birthday balloons" in fb.custom_feedback

    # 4. Verify category learning pattern updated
    fservice = FeedbackLearningService(db)
    context = fservice.get_historical_context(fb.original_category)
    assert isinstance(context, str)

    # 5. Verify model evaluation metrics
    eval_metrics = fservice.evaluate_model_performance()
    assert "precision" in eval_metrics
    assert "recall" in eval_metrics
    assert "f1_score" in eval_metrics
    assert "accuracy" in eval_metrics
    assert eval_metrics["precision"] > 0.0

    # 6. Test GET endpoints
    get_fb = client.get("/api/v1/images/feedbacks")
    assert get_fb.status_code == 200
    assert len(get_fb.json()) > 0

    get_eval = client.get("/api/v1/images/evaluation")
    assert get_eval.status_code == 200
    assert "f1_score" in get_eval.json()

    db.close()
