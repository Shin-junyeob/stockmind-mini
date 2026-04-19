"""
backtest.py - 학습된 앙상블 모델 백테스팅

기존 학습된 모델을 고정(frozen)하고, 과거 날짜 범위에 대한
예측 정확도를 계산한다 (fixed-model simulation).

실행:
    PYTHONPATH=src python src/ml/backtest.py
"""

import logging
import os
import pickle
from datetime import date

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from ml.train_ensemble import find_latest, get_proba_a, get_proba_b, get_proba_c
from ml.xgb_model import predict_xgb

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')


def run_backtest(
    ticker: str,
    start_date: date,
    end_date: date,
    threshold: float = 0.5,
) -> dict:
    """
    학습된 앙상블 모델로 start_date ~ end_date 구간 백테스팅.

    - threshold: 해당 값 이상(up) 또는 이하(down)인 날만 "거래"로 간주.
                 traded_accuracy 는 threshold 필터 적용 후 정확도.

    반환 형식:
    {
        "ticker":          str,
        "start_date":      str,
        "end_date":        str,
        "threshold":       float,
        "n_total":         int,    # 구간 내 거래일 수
        "n_traded":        int,    # threshold 신호 발생 날 수
        "accuracy":        float,  # 전체 정확도
        "traded_accuracy": float | None,
        "up_precision":    float,
        "up_recall":       float,
        "up_f1":           float,
        "daily_results":   list[dict],
    }
    """
    logger.info(
        f"[{ticker}] 백테스팅 시작: {start_date} ~ {end_date}, threshold={threshold}"
    )

    # ── 1. 각 모델 전체 예측 확률 수집 ────────────────────────
    df_a = get_proba_a(ticker)
    df_b = get_proba_b(ticker)
    df_c = get_proba_c(ticker)

    # ── 2. 날짜 기준 inner join (공통 구간) ───────────────────
    df = (
        df_a[["date", "proba_a", "y"]]
        .merge(df_b[["date", "proba_b"]], on="date", how="inner")
        .merge(df_c[["date", "proba_c"]], on="date", how="inner")
        .sort_values("date")
        .reset_index(drop=True)
    )

    # ── 3. 앙상블 모델 로드 ───────────────────────────────────
    xgb_path = find_latest(os.path.join(MODEL_DIR, f"{ticker}_ensemble_xgb_*.pkl"))
    with open(xgb_path, "rb") as f:
        ensemble_model = pickle.load(f)

    # ── 4. 앙상블 예측 ────────────────────────────────────────
    X = df[["proba_a", "proba_b", "proba_c"]].values.astype(np.float32)
    preds_all, proba_all = predict_xgb(ensemble_model, X)

    up_proba_all = proba_all[:, 1] if proba_all.shape[1] >= 2 else proba_all[:, 0]
    df["up_probability"] = up_proba_all
    df["prediction"]     = ["up" if p == 1 else "down" for p in preds_all]
    df["actual"]         = ["up" if y == 1 else "down" for y in df["y"]]

    # ── 5. 날짜 범위 필터 ─────────────────────────────────────
    start_ts = pd.Timestamp(start_date)
    end_ts   = pd.Timestamp(end_date)
    mask     = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    df_range = df[mask].reset_index(drop=True)

    if len(df_range) == 0:
        logger.warning(f"[{ticker}] 해당 기간 데이터 없음")
        return _empty_result(ticker, start_date, end_date, threshold)

    # ── 6. 전체 성능 지표 ─────────────────────────────────────
    y_true = df_range["y"].values
    y_pred = [1 if p == "up" else 0 for p in df_range["prediction"]]

    acc         = float(accuracy_score(y_true, y_pred))
    up_prec     = float(precision_score(y_true, y_pred, pos_label=1, zero_division=0))
    up_rec      = float(recall_score(y_true, y_pred, pos_label=1, zero_division=0))
    up_f1_val   = float(f1_score(y_true, y_pred, pos_label=1, zero_division=0))

    # ── 7. threshold 필터 성능 ────────────────────────────────
    traded_mask = (
        (df_range["up_probability"] >= threshold) |
        (df_range["up_probability"] <= 1 - threshold)
    )
    df_traded  = df_range[traded_mask]
    n_traded   = len(df_traded)

    if n_traded > 0:
        y_true_t = df_traded["y"].values
        y_pred_t = [1 if p == "up" else 0 for p in df_traded["prediction"]]
        traded_acc: float | None = round(float(accuracy_score(y_true_t, y_pred_t)), 4)
    else:
        traded_acc = None

    # ── 8. 일별 결과 리스트 ───────────────────────────────────
    daily_results = [
        {
            "date":           str(row["date"].date()),
            "direction":      row["prediction"],
            "actual":         row["actual"],
            "up_probability": round(float(row["up_probability"]), 4),
            "is_correct":     row["prediction"] == row["actual"],
        }
        for _, row in df_range.iterrows()
    ]

    logger.info(
        f"[{ticker}] 백테스팅 완료: n={len(df_range)}, "
        f"accuracy={acc:.4f}, up_f1={up_f1_val:.4f}, "
        f"n_traded={n_traded}, traded_accuracy={traded_acc}"
    )

    return {
        "ticker":          ticker,
        "start_date":      str(start_date),
        "end_date":        str(end_date),
        "threshold":       threshold,
        "n_total":         len(df_range),
        "n_traded":        n_traded,
        "accuracy":        round(acc, 4),
        "traded_accuracy": traded_acc,
        "up_precision":    round(up_prec, 4),
        "up_recall":       round(up_rec, 4),
        "up_f1":           round(up_f1_val, 4),
        "daily_results":   daily_results,
    }


def _empty_result(ticker: str, start_date: date, end_date: date, threshold: float) -> dict:
    return {
        "ticker":          ticker,
        "start_date":      str(start_date),
        "end_date":        str(end_date),
        "threshold":       threshold,
        "n_total":         0,
        "n_traded":        0,
        "accuracy":        None,
        "traded_accuracy": None,
        "up_precision":    None,
        "up_recall":       None,
        "up_f1":           None,
        "daily_results":   [],
    }


if __name__ == "__main__":
    import sys
    from datetime import date as dt

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    from settings import TICKERS
    for t in TICKERS:
        result = run_backtest(t, dt(2024, 1, 1), dt(2024, 12, 31), threshold=0.55)
        print(
            f"\n[{t}] accuracy={result['accuracy']} "
            f"traded_accuracy={result['traded_accuracy']} "
            f"n={result['n_total']} n_traded={result['n_traded']}"
        )
