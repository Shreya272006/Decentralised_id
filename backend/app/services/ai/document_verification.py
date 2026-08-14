"""
Document verification pipeline.

Uses OpenCV for structural/tampering artifact analysis and Tesseract
OCR for text extraction. This module operates on decrypted image bytes
held only in memory for the duration of the request — callers are
responsible for encrypting the source file at rest and never logging
raw bytes or extracted PII fields.

Production note: the tamper-detection heuristics below (edge/font
consistency, noise-variance analysis, copy-move artifact scan) are
classical computer-vision techniques suitable as a real first line of
defense. A production system would additionally run a trained
forgery-classification model (e.g. a fine-tuned CNN) behind the same
`analyze_document()` interface.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image


@dataclass
class DocumentAnalysisResult:
    ocr_extracted_fields: dict
    tamper_indicators: dict
    tamper_risk_score: float  # 0.0 (clean) .. 1.0 (highly suspicious)


ID_NUMBER_PATTERN = re.compile(r"\b[A-Z0-9]{6,12}\b")
DATE_PATTERN = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b")


def _load_image(image_bytes: bytes) -> np.ndarray:
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _noise_variance_map(gray: np.ndarray, block: int = 32) -> float:
    """
    Splits the image into blocks and measures the variance of local
    Laplacian noise. Spliced/edited regions often show discontinuous
    noise variance compared to the rest of an authentic photograph.
    """
    h, w = gray.shape
    variances = []
    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            patch = gray[y : y + block, x : x + block]
            lap = cv2.Laplacian(patch, cv2.CV_64F)
            variances.append(lap.var())
    if len(variances) < 2:
        return 0.0
    variances = np.array(variances)
    # Coefficient of variation across blocks — high spread suggests
    # inconsistent local sharpness/noise, a common splicing artifact.
    mean = variances.mean() + 1e-6
    return float(variances.std() / mean)


def _edge_density_consistency(gray: np.ndarray) -> float:
    """
    Detects abrupt edge-density discontinuities that can indicate
    pasted text blocks or overwritten fields (font/kerning tampering).
    """
    edges = cv2.Canny(gray, 60, 160)
    h, w = edges.shape
    strip_h = max(h // 8, 1)
    densities = []
    for y in range(0, h - strip_h, strip_h):
        strip = edges[y : y + strip_h, :]
        densities.append(np.count_nonzero(strip) / strip.size)
    if len(densities) < 2:
        return 0.0
    densities = np.array(densities)
    return float(densities.std() / (densities.mean() + 1e-6))


def _copy_move_score(gray: np.ndarray) -> float:
    """
    Lightweight copy-move forgery indicator using ORB keypoint matching
    against the image itself: authentic photos rarely contain many
    near-duplicate keypoint patches; edited documents that clone parts
    of the background/photo to hide alterations often do.
    """
    orb = cv2.ORB_create(nfeatures=500)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if descriptors is None or len(keypoints) < 20:
        return 0.0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(descriptors, descriptors, k=2)
    duplicate_like = 0
    for m in matches:
        if len(m) < 2:
            continue
        best, second = m[0], m[1]
        # A very close second-best match (excluding self-match) that is
        # also spatially distant suggests a duplicated region.
        if best.distance < 0.9 * second.distance and best.queryIdx != best.trainIdx:
            p1 = np.array(keypoints[best.queryIdx].pt)
            p2 = np.array(keypoints[best.trainIdx].pt)
            if np.linalg.norm(p1 - p2) > 25:
                duplicate_like += 1
    return float(min(duplicate_like / max(len(keypoints), 1), 1.0))


def extract_ocr_fields(bgr_image: np.ndarray) -> dict:
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    raw_text = pytesseract.image_to_string(gray)

    dates_found = DATE_PATTERN.findall(raw_text)
    ids_found = ID_NUMBER_PATTERN.findall(raw_text.upper())

    # Only non-sensitive, masked derivatives are returned — never the
    # full raw OCR text, which may contain the unmasked ID number.
    masked_ids = [f"{'*' * max(len(i) - 4, 2)}{i[-4:]}" for i in ids_found[:3]]

    return {
        "dates_detected": dates_found[:3],
        "id_like_tokens_masked": masked_ids,
        "text_line_count": len([l for l in raw_text.splitlines() if l.strip()]),
        "ocr_confidence_hint": "low" if len(raw_text.strip()) < 20 else "normal",
    }


def analyze_document(image_bytes: bytes) -> DocumentAnalysisResult:
    bgr = _load_image(image_bytes)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    noise_score = _noise_variance_map(gray)
    edge_score = _edge_density_consistency(gray)
    copy_move_score = _copy_move_score(gray)

    ocr_fields = extract_ocr_fields(bgr)

    # Weighted aggregation of independent tamper signals into [0, 1].
    tamper_risk = min(
        1.0,
        0.40 * min(noise_score / 2.5, 1.0)
        + 0.35 * min(edge_score / 1.5, 1.0)
        + 0.25 * copy_move_score,
    )

    indicators = {
        "noise_variance_inconsistency": round(noise_score, 4),
        "edge_density_inconsistency": round(edge_score, 4),
        "copy_move_similarity": round(copy_move_score, 4),
        "flags": [],
    }
    if noise_score > 1.5:
        indicators["flags"].append("inconsistent_noise_pattern")
    if edge_score > 1.0:
        indicators["flags"].append("possible_font_or_edit_artifact")
    if copy_move_score > 0.15:
        indicators["flags"].append("possible_copy_move_region")

    return DocumentAnalysisResult(
        ocr_extracted_fields=ocr_fields,
        tamper_indicators=indicators,
        tamper_risk_score=round(tamper_risk, 4),
    )
