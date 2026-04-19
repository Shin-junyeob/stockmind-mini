"""
tune_threshold.py - 앙상블 임계값 튜닝

backtest 기반으로 threshold 0.50 ~ 0.70 을 탐색하고,
traded_accuracy(신호 발생 날의 정확도)를 최대화하는 최적값을
models/{ticker}_threshold.json 에 저장한다.

조건: coverage(n_traded / n_total) >= MIN_COVERAGE 를 만족해야 채택.
커버리지가 너무 낮으면 실용성이 없으므로 기본 threshold(0.5) 유지.

실행:
    PYTHONPATH=src python src/ml/tune_threshold.py
"""

import json
import logging
import os
import sys
from datetime import date

import numpy as np
import pandas as pd

from ml.backtest import run_backtest

logger = logging.getLogger(__name__)

MODEL_DIR    = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
MIN_COVERAGE = 0.3    # traded 날이 전체의 30% 이상이어야 채택
THRESHOLD_STEP = 0.01
THRESHOLD_RANGE = np.arange(0.50, 0.71, THRESHOLD_STEP)


def tune_threshold(
    ticker: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    start_date ~ end_date 기간에 대해 threshold를 탐색하고
    최적값을 models/{ticker}_threshold.json 에 저장.

    반환:
    {
        "ticker":           str,
        "best_threshold":   float,
        "best_accuracy":    float,
        "coverage":         float,
        "n_total":          int,
        "n_traded":         int,
        "search_results":   list[dict],  # 각 threshold별 결과
    }
    """
    logger.info(
        f"[{ticker}] 임계값 튜닝 시작: {start_date} ~ {end_date}, "
        f"탐색 범위 {THRESHOLD_RANGE[0]:.2f} ~ {THRESHOLD_RANGE[-1]:.2f}"
    )

    search_results = []

    for t in THRESHOLD_RANGE:
        t = round(float(t), 2)
        result = run_backtest(ticker, start_date, end_date, threshold=t)

        n_total  = result["n_total"]
        n_traded = result["n_traded"]
        t_acc    = result["traded_accuracy"]
        coverage = n_traded / n_total if n_total > 0 else 0.0

        search_results.append({
            "threshold":       t,
            "traded_accuracy": t_acc,
            "coverage":        round(coverage, 4),
            "n_traded":        n_traded,
            "n_total":         n_total,
        })

    # ── 커버리지 조건 만족하는 후보만 추림 ──────────────────────
    candidates = [
        r for r in search_results
        if r["coverage"] >= MIN_COVERAGE and r["traded_accuracy"] is not None
    ]

    if not candidates:
        logger.warning(
            f"[{ticker}] 커버리지 {MIN_COVERAGE:.0%} 이상 후보 없음 → 기본값 0.5 사용"
        )
        best_threshold = 0.5
        best_accuracy  = next(
            (r["traded_accuracy"] for r in search_results if r["threshold"] == 0.5), None
        )
        coverage       = next(
            (r["coverage"] for r in search_results if r["threshold"] == 0.5), 1.0
        )
        n_traded = next(
            (r["n_traded"] for r in search_results if r["threshold"] == 0.5), 0
        )
    else:
        best = max(candidates, key=lambda r: r["traded_accuracy"])
        best_threshold = best["threshold"]
        best_accuracy  = best["traded_accuracy"]
        coverage       = best["coverage"]
        n_traded       = best["n_traded"]

    n_total = search_results[0]["n_total"] if search_results else 0

    logger.info(
        f"[{ticker}] 최적 threshold={best_threshold:.2f} | "
        f"traded_accuracy={best_accuracy} | "
        f"coverage={coverage:.1%} ({n_traded}/{n_total})"
    )

    # ── JSON 저장 ─────────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    threshold_path = os.path.join(MODEL_DIR, f"{ticker}_threshold.json")
    payload = {
        "ticker":         ticker,
        "best_threshold": best_threshold,
        "best_accuracy":  best_accuracy,
        "coverage":       coverage,
        "n_total":        n_total,
        "n_traded":       n_traded,
        "tuned_on":       {"start": str(start_date), "end": str(end_date)},
    }
    with open(threshold_path, "w") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"[{ticker}] 임계값 저장 완료: {threshold_path}")

    return {**payload, "search_results": search_results}


def load_threshold(ticker: str) -> float:
    """
    저장된 threshold 반환. 파일 없으면 기본값 0.5.
    predictor.py 등 다른 모듈에서 임포트해서 사용.
    """
    path = os.path.join(MODEL_DIR, f"{ticker}_threshold.json")
    if not os.path.exists(path):
        return 0.5
    with open(path) as f:
        data = json.load(f)
    return float(data.get("best_threshold", 0.5))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    from settings import TICKERS

    # 최근 1년 데이터로 튜닝 (out-of-sample에 가까운 구간)
    from datetime import date as dt, timedelta
    end   = dt.today()
    start = dt(end.year - 1, end.month, end.day)

    for ticker in TICKERS:
        result = tune_threshold(ticker, start, end)
        print(
            f"\n[{ticker}] best_threshold={result['best_threshold']} | "
            f"traded_accuracy={result['best_accuracy']} | "
            f"coverage={result['coverage']:.1%}"
        )
