import pytest

from app.services.generation import ReviewDraft, _clean_review_text, _json_object


def test_json_object_extracts_fenced_json() -> None:
    parsed = _json_object('```json\n{"review_text": "This is a grounded review with enough detail to pass validation."}\n```')
    assert ReviewDraft.model_validate(parsed).review_text.startswith("This is")


def test_clean_review_rejects_ai_framing() -> None:
    with pytest.raises(ValueError):
        _clean_review_text("As an AI language model, I would rate this item highly.")
