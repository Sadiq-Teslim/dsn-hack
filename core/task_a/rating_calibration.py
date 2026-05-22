from __future__ import annotations

from app.services.text_utils import clamp, stable_round
from core.schemas import RatingCalibration, UserProfile


def calibrate_rating(profile: UserProfile, sentiment: float, catalog_rating: float = 3.8) -> RatingCalibration:
    sentiment = clamp(sentiment, 0, 1)
    sentiment_rating = 1 + sentiment * 4
    user_mean = profile.rating_mean or 3.8
    strictness_shift = (user_mean - 3.8) * 0.45
    variance_shift = 0.0
    if profile.rating_std < 0.45 and profile.history_count >= 2:
        variance_shift = (user_mean - sentiment_rating) * 0.20
    raw_rating = 0.62 * sentiment_rating + 0.23 * catalog_rating + 0.15 * user_mean
    calibrated = raw_rating + strictness_shift + variance_shift
    calibrated = stable_round(clamp(calibrated, 1.0, 5.0), 1)
    return RatingCalibration(
        sentiment=stable_round(sentiment),
        raw_rating=stable_round(clamp(raw_rating, 1.0, 5.0), 2),
        calibrated_rating=calibrated,
        explanation=(
            f"Sentiment {sentiment:.2f} maps to raw {raw_rating:.2f}; user mean {user_mean:.2f}, "
            f"std {profile.rating_std:.2f}, and bias {profile.rating_bias:+.2f} calibrate it to "
            f"{calibrated:.1f} stars."
        ),
    )
