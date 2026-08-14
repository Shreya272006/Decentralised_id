import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentVerifyResponse(BaseModel):
    document_upload_id: uuid.UUID
    document_type: str
    ocr_extracted_fields: dict
    tamper_indicators: dict
    tamper_risk_score: float
    status: str


class FaceVerifyResponse(BaseModel):
    face_match_id: uuid.UUID
    similarity_score: float
    match_passed: bool
    threshold: float


class LivenessCheckResponse(BaseModel):
    liveness_score: float
    liveness_passed: bool
    signals: dict


class FraudScoreRequest(BaseModel):
    document_upload_id: uuid.UUID
    face_match_id: uuid.UUID


class FraudScoreResponse(BaseModel):
    fraud_score_id: uuid.UUID
    document_score: float
    face_score: float
    behavioral_score: float
    overall_score: float
    status: str  # APPROVED | REVIEW | REJECTED
    signals: dict
