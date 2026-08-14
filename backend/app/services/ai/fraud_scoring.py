"""
Multi-factor fraud risk aggregation engine.

Combines document tamper-risk, face-match confidence, and behavioral
signals (velocity of attempts, IP volatility, repeated failures) into
a single weighted risk score, producing an actionable status.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import FraudScore


@dataclass
class BehavioralSignals:
    attempts_last_hour: int
    distinct_ips_last_24h: int
    consecutive_failures: int


@dataclass
class FraudAssessment:
    document_score: float
    face_score: float
    behavioral_score: float
    overall_score: float
    status: str  # APPROVED | REVIEW | REJECTED
    signals: dict


def compute_behavioral_signals(db: Session, user_id: str) -> BehavioralSignals:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    one_day_ago = datetime.utcnow() - timedelta(hours=24)

    attempts_last_hour = (
        db.query(func.count(FraudScore.id))
        .filter(FraudScore.user_id == user_id, FraudScore.created_at >= one_hour_ago)
        .scalar()
        or 0
    )

    distinct_ips = (
        db.query(func.count(func.distinct(FraudScore.ip_address)))
        .filter(FraudScore.user_id == user_id, FraudScore.created_at >= one_day_ago)
        .scalar()
        or 0
    )

    recent = (
        db.query(FraudScore.status)
        .filter(FraudScore.user_id == user_id)
        .order_by(FraudScore.created_at.desc())
        .limit(5)
        .all()
    )
    consecutive_failures = 0
    for (status_val,) in recent:
        if status_val == "REJECTED":
            consecutive_failures += 1
        else:
            break

    return BehavioralSignals(
        attempts_last_hour=attempts_last_hour,
        distinct_ips_last_24h=distinct_ips,
        consecutive_failures=consecutive_failures,
    )


def _behavioral_risk(signals: BehavioralSignals) -> float:
    """Higher return value == riskier behavior, normalized to [0, 1]."""
    velocity_risk = min(signals.attempts_last_hour / 8.0, 1.0)  # >8 attempts/hr is maximally risky
    ip_risk = min(max(signals.distinct_ips_last_24h - 1, 0) / 4.0, 1.0)  # >5 distinct IPs/day maxes out
    failure_risk = min(signals.consecutive_failures / 3.0, 1.0)
    return round(0.45 * velocity_risk + 0.25 * ip_risk + 0.30 * failure_risk, 4)


def assess_fraud(
    *,
    document_tamper_risk: float,
    face_similarity_score: float,
    face_match_passed: bool,
    liveness_passed: bool,
    behavioral_signals: BehavioralSignals,
) -> FraudAssessment:
    document_score = round(document_tamper_risk, 4)

    # Face risk is high when match fails or liveness fails, regardless
    # of raw similarity — spoofed liveness must never be trusted.
    if not liveness_passed:
        face_score = 0.9
    elif not face_match_passed:
        face_score = round(1.0 - face_similarity_score, 4)
    else:
        face_score = round(max(0.0, 1.0 - face_similarity_score) * 0.5, 4)

    behavioral_score = _behavioral_risk(behavioral_signals)

    overall = round(0.40 * document_score + 0.40 * face_score + 0.20 * behavioral_score, 4)

    if overall >= settings.FRAUD_REJECT_THRESHOLD:
        status = "REJECTED"
    elif overall >= settings.FRAUD_REVIEW_THRESHOLD:
        status = "REVIEW"
    else:
        status = "APPROVED"

    signals = {
        "liveness_passed": liveness_passed,
        "face_match_passed": face_match_passed,
        "attempts_last_hour": behavioral_signals.attempts_last_hour,
        "distinct_ips_last_24h": behavioral_signals.distinct_ips_last_24h,
        "consecutive_failures": behavioral_signals.consecutive_failures,
    }

    return FraudAssessment(
        document_score=document_score,
        face_score=face_score,
        behavioral_score=behavioral_score,
        overall_score=overall,
        status=status,
        signals=signals,
    )
