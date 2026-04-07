"""
train_b.py - Model B 학습 오케스트레이터 (차트패턴 기반)

실행: PYTHONPATH=src python src/ml/train_b.py

전체 흐름:
1. DB에서 데이터 로드
2. 차트패턴 feature 생성
3. y값 재매핑
4. XGBoost 학습
5. 모델 저장
6. 최종 성능 평가
"""

import logging
import sys
import os
import pickle
from datetime import datetime

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, precision_score, f1_score

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from ml.chart_features import load_data, build_chart_dataset
from ml.xgb_model import train_xgb, predict_xgb
from settings import TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
LABEL_NAMES = {0: "down", 1: "up"}


def remap_labels(y: np.ndarray) -> tuple[np.ndarray, dict, dict]:
    """y값을 0부터 연속적으로 재매핑."""
    unique_classes = sorted(np.unique(y).tolist())
    class_map = {c: i for i, c in enumerate(unique_classes)}
    inv_map   = {i: c for c, i in class_map.items()}
    y_mapped  = np.array([class_map[c] for c in y], dtype=np.int64)

    label_str = {i: LABEL_NAMES[c] for c, i in class_map.items()}
    logger.info(f"[train_b] 클래스 재매핑: {label_str}")
    return y_mapped, class_map, inv_map


def train_pipeline_b(ticker: str) -> dict:
    """Model B 전체 학습 파이프라인."""
    logger.info(f"=== [{ticker}] Model B 학습 파이프라인 시작 ===")

    # ── 1. 데이터 로드 ────────────────────────────────────────
    df = load_data(ticker)
    if len(df) < 50:
        logger.error(f"[{ticker}] 데이터 부족: {len(df)}행 (최소 50행 필요)")
        return {}

    # ── 2. 차트패턴 feature 생성 ──────────────────────────────
    X, y, dates = build_chart_dataset(df)

    # ── 3. y값 재매핑 ─────────────────────────────────────────
    y_mapped, class_map, inv_map = remap_labels(y)

    # ── 4. XGBoost 학습 ───────────────────────────────────────
    xgb_model = train_xgb(X, y_mapped)

    # ── 5. 최종 성능 평가 ─────────────────────────────────────
    split      = int(len(X) * 0.8)
    X_test     = X[split:]
    y_test     = y_mapped[split:]

    preds_mapped, proba = predict_xgb(xgb_model, X_test)

    # 원본 label로 역매핑
    preds_orig  = np.array([inv_map[p] for p in preds_mapped])
    y_test_orig = np.array([inv_map[p] for p in y_test])

    up_precision = precision_score(y_test_orig, preds_orig, pos_label=1, zero_division=0)
    up_f1        = f1_score(y_test_orig, preds_orig, pos_label=1, zero_division=0)
    report = classification_report(
        y_test_orig, preds_orig,
        target_names=["down", "up"],
        labels=[0, 1],
        zero_division=0,
    )

    logger.info(f"[{ticker}] up Precision: {up_precision:.4f} | up F1: {up_f1:.4f}")
    logger.info(f"[{ticker}] 분류 리포트:\n{report}")

    # ── 6. 모델 저장 ──────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    xgb_path  = os.path.join(MODEL_DIR, f"{ticker}_b_xgb_{timestamp}.pkl")
    meta_path = os.path.join(MODEL_DIR, f"{ticker}_b_meta_{timestamp}.pkl")

    with open(xgb_path, "wb") as f:
        pickle.dump(xgb_model, f)

    with open(meta_path, "wb") as f:
        pickle.dump({"class_map": class_map, "inv_map": inv_map}, f)

    logger.info(f"[{ticker}] 모델 저장 완료")
    logger.info(f"  XGBoost → {xgb_path}")
    logger.info(f"  Meta    → {meta_path}")
    logger.info(f"=== [{ticker}] Model B 학습 파이프라인 완료 ===")

    return {
        "ticker":       ticker,
        "up_precision": up_precision,
        "up_f1":        up_f1,
        "report":       report,
    }


if __name__ == "__main__":
    results = {}
    for ticker in TICKERS:
        result = train_pipeline_b(ticker)
        if result:
            results[ticker] = result

    logger.info("=== 전체 Model B 학습 완료 ===")
    for ticker, result in results.items():
        logger.info(f"{ticker}: up_precision={result['up_precision']:.4f} | up_f1={result['up_f1']:.4f}")
