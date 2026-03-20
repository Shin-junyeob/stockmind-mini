"""
train.py - 학습 오케스트레이터

실행: PYTHONPATH=src python src/ml/train.py

전체 흐름:
1. DB에서 데이터 로드
2. Feature 엔지니어링
3. y값 전체 재매핑 (flat 없는 경우 대비)
4. LSTM 학습
5. LSTM 출력 + 테이블 feature 결합
6. XGBoost 학습
7. 모델 저장
8. 최종 성능 평가
"""

import logging
import sys
import os
import pickle
from datetime import datetime

import numpy as np
from sklearn.metrics import accuracy_score, classification_report

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from ml.features import load_data, build_sequences
from ml.lstm_model import train_lstm, predict_proba_lstm
from ml.xgb_model import build_xgb_features, train_xgb, predict_xgb
from settings import TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

# label 이름 매핑
LABEL_NAMES = {0: "down", 1: "flat", 2: "up"}


def remap_labels(y: np.ndarray) -> tuple[np.ndarray, dict, dict]:
    """
    y값을 0부터 연속적으로 재매핑.
    flat이 없는 경우: {0:'down', 2:'up'} → {0:'down', 1:'up'}

    Returns:
        y_mapped:    재매핑된 y
        class_map:   원본 → 재매핑 (예: {0:0, 2:1})
        inv_map:     재매핑 → 원본 (예: {0:0, 1:2})
    """
    unique_classes = sorted(np.unique(y).tolist())
    class_map = {c: i for i, c in enumerate(unique_classes)}
    inv_map   = {i: c for c, i in class_map.items()}
    y_mapped  = np.array([class_map[c] for c in y], dtype=np.int64)

    label_str = {i: LABEL_NAMES[c] for c, i in class_map.items()}
    logger.info(f"[train] 클래스 재매핑: {label_str}")
    return y_mapped, class_map, inv_map


def train_pipeline(ticker: str) -> dict:
    """
    ticker 하나에 대한 전체 학습 파이프라인 실행.
    """
    logger.info(f"=== [{ticker}] 학습 파이프라인 시작 ===")

    # ── 1. 데이터 로드 ────────────────────────────────────────
    df = load_data(ticker)
    if len(df) < 50:
        logger.error(f"[{ticker}] 데이터 부족: {len(df)}행 (최소 50행 필요)")
        return {}

    # ── 2. Feature 엔지니어링 ─────────────────────────────────
    X_seq, X_tab, y, dates, scaler = build_sequences(df)
    input_size = X_seq.shape[2]

    logger.info(f"[{ticker}] 클래스 분포: down={sum(y==0)} flat={sum(y==1)} up={sum(y==2)}")

    # ── 3. y값 전체 재매핑 ────────────────────────────────────
    y_mapped, class_map, inv_map = remap_labels(y)
    n_classes = len(class_map)

    # ── 4. LSTM 학습 ──────────────────────────────────────────
    lstm_model = train_lstm(
        X_seq=X_seq,
        y=y_mapped,
        input_size=input_size,
        epochs=50,
        batch_size=16,
        lr=1e-3,
    )

    # ── 5. LSTM 확률값 추출 ───────────────────────────────────
    lstm_proba = predict_proba_lstm(lstm_model, X_seq)
    logger.info(f"[{ticker}] LSTM 확률값 shape: {lstm_proba.shape}")

    # ── 6. XGBoost feature 결합 + 학습 ───────────────────────
    X_combined = build_xgb_features(lstm_proba, X_tab)
    xgb_model  = train_xgb(X_combined, y_mapped)

    # ── 7. 최종 성능 평가 ─────────────────────────────────────
    split    = int(len(X_combined) * 0.8)
    X_test   = X_combined[split:]
    y_test   = y_mapped[split:]

    preds_mapped, proba = predict_xgb(xgb_model, X_test)

    # 예측값을 원본 label로 역매핑
    preds_orig = np.array([inv_map[p] for p in preds_mapped])
    y_test_orig = np.array([inv_map[p] for p in y_test])

    acc = accuracy_score(y_test_orig, preds_orig)
    report = classification_report(
        y_test_orig, preds_orig,
        target_names=["down", "flat", "up"],
        labels=[0, 1, 2],
        zero_division=0,
    )

    logger.info(f"[{ticker}] 최종 테스트 정확도: {acc:.4f}")
    logger.info(f"[{ticker}] 분류 리포트:\n{report}")

    # ── 8. 모델 저장 ──────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    lstm_path   = os.path.join(MODEL_DIR, f"{ticker}_lstm_{timestamp}.pt")
    xgb_path    = os.path.join(MODEL_DIR, f"{ticker}_xgb_{timestamp}.pkl")
    scaler_path = os.path.join(MODEL_DIR, f"{ticker}_scaler_{timestamp}.pkl")
    meta_path   = os.path.join(MODEL_DIR, f"{ticker}_meta_{timestamp}.pkl")

    import torch
    torch.save(lstm_model.state_dict(), lstm_path)

    with open(xgb_path, "wb") as f:
        pickle.dump(xgb_model, f)

    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    # class_map, inv_map 저장 (예측 시 역매핑에 필요)
    with open(meta_path, "wb") as f:
        pickle.dump({"class_map": class_map, "inv_map": inv_map, "n_classes": n_classes}, f)

    logger.info(f"[{ticker}] 모델 저장 완료")
    logger.info(f"  LSTM   → {lstm_path}")
    logger.info(f"  XGBoost→ {xgb_path}")
    logger.info(f"  Scaler → {scaler_path}")
    logger.info(f"  Meta   → {meta_path}")
    logger.info(f"=== [{ticker}] 학습 파이프라인 완료 ===")

    return {
        "ticker":   ticker,
        "accuracy": acc,
        "report":   report,
    }


if __name__ == "__main__":
    results = {}
    for ticker in TICKERS:
        result = train_pipeline(ticker)
        if result:
            results[ticker] = result

    logger.info("=== 전체 학습 완료 ===")
    for ticker, result in results.items():
        logger.info(f"{ticker}: accuracy={result['accuracy']:.4f}")
