"""
train_ensemble.py - 앙상블 메타모델 학습

실행: PYTHONPATH=src python src/ml/train_ensemble.py

전체 흐름:
1. 저장된 Model A/B/C 로드 (가장 최신 파일 자동 선택)
2. 각 모델로 전체 데이터에 대한 up 확률 예측
3. 날짜 기준으로 정렬 + 공통 구간 추출
4. Meta XGBoost 학습 (입력: 세 모델의 up 확률)
5. 성능 평가 + 모델 저장
"""

import logging
import sys
import os
import pickle
import glob
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, precision_score, f1_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

import torch
from ml.features import load_data, build_sequences
from ml.chart_features import load_data as load_data_b, build_chart_dataset
from ml.sentiment_features import build_stage2_dataset, build_stage3_dataset, build_stage4_dataset
from ml.lstm_model import LSTMClassifier, predict_proba_lstm
from ml.xgb_model import build_xgb_features, train_xgb, predict_xgb
from settings import TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

PRICE_FEATURES = [
    "close", "volume", "price_change_pct",
    "ma5", "ma20", "ma60", "rsi",
    "ks11_close", "ixic_close", "vix_close",
]
WINDOW_SIZE = 20


def find_latest(pattern: str) -> str:
    """glob 패턴으로 가장 최신 파일 반환 (파일명에 날짜 포함 가정)."""
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"모델 파일 없음: {pattern}")
    return sorted(files)[-1]


def _up_proba(proba: np.ndarray) -> np.ndarray:
    """
    XGBoost predict_xgb가 반환하는 proba에서 up(class 1) 확률 추출.
    label_map = {"up": 1, "down": 0, "flat": 0} 이므로 index 1 = up.
    """
    if proba.shape[1] >= 2:
        return proba[:, 1]
    return proba[:, 0]


def get_proba_a(ticker: str) -> pd.DataFrame:
    """Model A (LSTM+XGBoost)로 전체 데이터에 대한 up 확률 반환."""
    logger.info(f"[{ticker}] Model A 예측 시작")

    lstm_path   = find_latest(os.path.join(MODEL_DIR, f"{ticker}_lstm_*.pt"))
    xgb_path    = find_latest(os.path.join(MODEL_DIR, f"{ticker}_xgb_*.pkl"))
    scaler_path = find_latest(os.path.join(MODEL_DIR, f"{ticker}_scaler_*.pkl"))
    meta_path   = find_latest(os.path.join(MODEL_DIR, f"{ticker}_meta_*.pkl"))

    with open(scaler_path, "rb") as f:
        scaler: StandardScaler = pickle.load(f)
    with open(xgb_path, "rb") as f:
        xgb_model = pickle.load(f)
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)

    n_classes  = meta["n_classes"]
    input_size = len(PRICE_FEATURES)

    lstm_model = LSTMClassifier(input_size=input_size, num_classes=n_classes)
    lstm_model.load_state_dict(torch.load(lstm_path, map_location="cpu", weights_only=True))
    lstm_model.eval()

    # 데이터 + 스케일링
    df = load_data(ticker)
    X_seq, X_tab, y, dates = build_sequences(df)

    n_features = input_size
    X_seq_scaled = scaler.transform(
        X_seq.reshape(-1, n_features)
    ).reshape(-1, WINDOW_SIZE, n_features).astype(np.float32)
    X_tab_scaled = scaler.transform(X_tab).astype(np.float32)

    # LSTM 확률 → XGBoost 입력 → up 확률
    lstm_proba = predict_proba_lstm(lstm_model, X_seq_scaled)
    X_combined = build_xgb_features(lstm_proba, X_tab_scaled)
    _, proba = predict_xgb(xgb_model, X_combined)

    result = pd.DataFrame({
        "date":    pd.to_datetime(dates),
        "proba_a": _up_proba(proba),
        "y":       y,
    })
    logger.info(f"[{ticker}] Model A 예측 완료: {len(result)}행")
    return result


def get_proba_b(ticker: str) -> pd.DataFrame:
    """Model B (차트패턴 XGBoost)로 전체 데이터에 대한 up 확률 반환."""
    logger.info(f"[{ticker}] Model B 예측 시작")

    xgb_path  = find_latest(os.path.join(MODEL_DIR, f"{ticker}_b_xgb_*.pkl"))

    with open(xgb_path, "rb") as f:
        xgb_model = pickle.load(f)

    df = load_data_b(ticker)
    X, y, dates = build_chart_dataset(df)

    _, proba = predict_xgb(xgb_model, X)

    result = pd.DataFrame({
        "date":    pd.to_datetime(dates),
        "proba_b": _up_proba(proba),
        "y":       y,
    })
    logger.info(f"[{ticker}] Model B 예측 완료: {len(result)}행")
    return result


def get_proba_c(ticker: str) -> pd.DataFrame:
    """Model C (감성 XGBoost)로 전체 데이터에 대한 up 확률 반환."""
    logger.info(f"[{ticker}] Model C 예측 시작")

    xgb_path  = find_latest(os.path.join(MODEL_DIR, f"{ticker}_c_xgb_*.pkl"))
    meta_path = find_latest(os.path.join(MODEL_DIR, f"{ticker}_c_meta_*.pkl"))

    with open(xgb_path, "rb") as f:
        xgb_model = pickle.load(f)
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)

    best_stage = meta["best_stage"]
    logger.info(f"[{ticker}] Model C best_stage: {best_stage}")

    stage_fn = {
        "stage2": build_stage2_dataset,
        "stage3": build_stage3_dataset,
        "stage4": build_stage4_dataset,
    }
    X, y, dates = stage_fn[best_stage](ticker)

    _, proba = predict_xgb(xgb_model, X)

    result = pd.DataFrame({
        "date":    pd.to_datetime(dates),
        "proba_c": _up_proba(proba),
        "y":       y,
    })
    logger.info(f"[{ticker}] Model C 예측 완료: {len(result)}행")
    return result


def train_ensemble(ticker: str) -> dict:
    logger.info(f"=== [{ticker}] 앙상블 학습 시작 ===")

    # ── 1. 각 모델 확률 수집 ─────────────────────────────────
    df_a = get_proba_a(ticker)
    df_b = get_proba_b(ticker)
    df_c = get_proba_c(ticker)

    # ── 2. 날짜 기준 inner join (공통 구간 추출) ──────────────
    df = (
        df_a[["date", "proba_a", "y"]]
        .merge(df_b[["date", "proba_b"]], on="date", how="inner")
        .merge(df_c[["date", "proba_c"]], on="date", how="inner")
        .sort_values("date")
        .reset_index(drop=True)
    )

    logger.info(
        f"[{ticker}] 공통 구간: {len(df)}행 "
        f"({df['date'].min().date()} ~ {df['date'].max().date()})"
    )
    logger.info(
        f"[{ticker}] Model A: {len(df_a)}행 / "
        f"Model B: {len(df_b)}행 / Model C: {len(df_c)}행"
    )

    if len(df) < 50:
        logger.error(f"[{ticker}] 공통 데이터 부족: {len(df)}행 (최소 50행 필요)")
        return {}

    # ── 3. 메타 feature + label ──────────────────────────────
    X = df[["proba_a", "proba_b", "proba_c"]].values.astype(np.float32)
    y = df["y"].values.astype(np.int64)

    logger.info(f"[{ticker}] 클래스 분포: down={sum(y==0)} up={sum(y==1)}")

    # ── 4. 시계열 순서 유지 80/20 split ─────────────────────
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    logger.info(f"[{ticker}] train={len(X_train)} test={len(X_test)}")

    # ── 5. Meta XGBoost 학습 ─────────────────────────────────
    ensemble_model = train_xgb(X_train, y_train)

    # ── 6. 성능 평가 ─────────────────────────────────────────
    preds, _ = predict_xgb(ensemble_model, X_test)

    up_precision = precision_score(y_test, preds, pos_label=1, zero_division=0)
    up_f1        = f1_score(y_test, preds, pos_label=1, zero_division=0)
    report = classification_report(
        y_test, preds,
        target_names=["down", "up"],
        labels=[0, 1],
        zero_division=0,
    )

    logger.info(f"[{ticker}] 앙상블 up Precision: {up_precision:.4f} | up F1: {up_f1:.4f}")
    logger.info(f"[{ticker}] 분류 리포트:\n{report}")

    # ── 7. 모델 저장 ──────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    xgb_path  = os.path.join(MODEL_DIR, f"{ticker}_ensemble_xgb_{timestamp}.pkl")
    meta_path = os.path.join(MODEL_DIR, f"{ticker}_ensemble_meta_{timestamp}.pkl")

    with open(xgb_path, "wb") as f:
        pickle.dump(ensemble_model, f)
    with open(meta_path, "wb") as f:
        pickle.dump({
            "features":  ["proba_a", "proba_b", "proba_c"],
            "class_map": {0: 0, 1: 1},
            "inv_map":   {0: 0, 1: 1},
        }, f)

    logger.info(f"[{ticker}] 앙상블 모델 저장 완료")
    logger.info(f"  XGBoost → {xgb_path}")
    logger.info(f"  Meta    → {meta_path}")
    logger.info(f"=== [{ticker}] 앙상블 학습 완료 ===")

    return {
        "ticker":       ticker,
        "up_precision": up_precision,
        "up_f1":        up_f1,
        "n_samples":    len(df),
        "report":       report,
    }


if __name__ == "__main__":
    results = {}
    for ticker in TICKERS:
        result = train_ensemble(ticker)
        if result:
            results[ticker] = result

    logger.info("\n" + "=" * 60)
    logger.info("전체 앙상블 학습 완료")
    logger.info("=" * 60)
    for ticker, res in results.items():
        logger.info(
            f"{ticker}: up_precision={res['up_precision']:.4f} | "
            f"up_f1={res['up_f1']:.4f} | "
            f"공통 샘플={res['n_samples']}"
        )
