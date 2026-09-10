"""Evaluation against ground truth (offline)."""

from __future__ import annotations

import json

from dq_platform.config import RAW_DIR


def load_ground_truth() -> list[dict]:
    path = RAW_DIR / "ground_truth_anomalies.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_detection(detected_types: list[str]) -> dict:
    """Compare detected anomaly types vs ground truth."""
    gt = load_ground_truth()
    gt_types = {a["anomaly_type"] for a in gt}
    detected = set(detected_types)
    tp = len(gt_types & detected)
    fp = len(detected - gt_types)
    fn = len(gt_types - detected)
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
