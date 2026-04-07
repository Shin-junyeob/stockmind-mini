"""
train_c.py - Model C 비교 실험 + 최종 학습

실행: PYTHONPATH=src python src/ml/train_c.py

stage2: Fear & Greed만 (5년치)
stage3: Fear & Greed + VIX (5년치)  ← 기대 최우수
stage4: 뉴스 감성만 (2개월치)

세 결과를 비교하고, 가장 좋은 stage의 모델을 최종 Model C로 저장.
"""

import logging
import sys
import os
import pickle
from datetime import datetime

import numpy as np
from sklearn.metrics import classification_report, precision_score, f1_score

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from ml.sentiment_features import build_stage2_dataset, build_stage3_dataset, build_stage4_dataset
from ml.xgb_model import train_xgb, predict_xgb
from settings import TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')


def run_experiment(ticker: str, stage: str, X: np.ndarray, y: np.ndarray) -> dict:
    """단일 stage 실험: 학습 + 평가."""
    if len(X) < 50:
        logger.warning(f"[{ticker}][{stage}] 데이터 부족 ({len(X)}행) → 스킵")
        return {}

    # 클래스 재매핑
    unique = sorted(np.unique(y).tolist())
    class_map = {c: i for i, c in enumerate(unique)}
    inv_map   = {i: c for c, i in class_map.items()}
    y_mapped  = np.array([class_map[c] for c in y], dtype=np.int64)

    # 학습
    xgb_model = train_xgb(X, y_mapped)

    # 평가 (마지막 20%)
    split  = int(len(X) * 0.8)
    X_test = X[split:]
    y_test = y_mapped[split:]

    preds_mapped, _ = predict_xgb(xgb_model, X_test)
    preds_orig  = np.array([inv_map[p] for p in preds_mapped])
    y_test_orig = np.array([inv_map[p] for p in y_test])

    up_precision = precision_score(y_test_orig, preds_orig, pos_label=1, zero_division=0)
    up_f1        = f1_score(y_test_orig, preds_orig, pos_label=1, zero_division=0)
    report = classification_report(
        y_test_orig, preds_orig,
        target_names=["down", "up"], labels=[0, 1], zero_division=0,
    )

    logger.info(f"[{ticker}][{stage}] up Precision: {up_precision:.4f} | up F1: {up_f1:.4f}")
    logger.info(f"[{ticker}][{stage}] 분류 리포트:\n{report}")

    return {
        "stage":        stage,
        "up_precision": up_precision,
        "up_f1":        up_f1,
        "model":        xgb_model,
        "class_map":    class_map,
        "inv_map":      inv_map,
    }


def train_pipeline_c(ticker: str) -> dict:
    logger.info(f"=== [{ticker}] Model C 비교 실험 시작 ===")

    # ── 데이터 로드 ───────────────────────────────────────────
    try:
        X2, y2, _ = build_stage2_dataset(ticker)
    except Exception as e:
        logger.error(f"stage2 데이터 로드 실패: {e}")
        X2, y2 = np.array([]), np.array([])

    try:
        X3, y3, _ = build_stage3_dataset(ticker)
    except Exception as e:
        logger.error(f"stage3 데이터 로드 실패: {e}")
        X3, y3 = np.array([]), np.array([])

    try:
        X4, y4, _ = build_stage4_dataset(ticker)
    except Exception as e:
        logger.error(f"stage4 데이터 로드 실패: {e}")
        X4, y4 = np.array([]), np.array([])

    # ── 비교 실험 ─────────────────────────────────────────────
    results = {}
    for stage, X, y in [("stage2", X2, y2), ("stage3", X3, y3), ("stage4", X4, y4)]:
        if len(X) > 0:
            res = run_experiment(ticker, stage, X, y)
            if res:
                results[stage] = res

    if not results:
        logger.error(f"[{ticker}] 모든 stage 실패")
        return {}

    # ── 결과 비교 ─────────────────────────────────────────────
    logger.info(f"\n{'='*50}")
    logger.info(f"[{ticker}] 비교 결과 요약")
    logger.info(f"{'stage':<10} {'up_precision':>14} {'up_f1':>8}")
    logger.info(f"{'-'*34}")
    for stage, res in results.items():
        marker = " ◀ best" if res["up_f1"] == max(r["up_f1"] for r in results.values()) else ""
        logger.info(f"{stage:<10} {res['up_precision']:>14.4f} {res['up_f1']:>8.4f}{marker}")
    logger.info(f"{'='*50}\n")

    # ── 최고 stage 선택 (up_f1 기준) ─────────────────────────
    best_stage = max(results, key=lambda s: results[s]["up_f1"])
    best = results[best_stage]
    logger.info(f"[{ticker}] 최종 선택: {best_stage} (up_f1={best['up_f1']:.4f})")

    # ── 모델 저장 ─────────────────────────────────────────────
    os.makedirs(MODEL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    xgb_path  = os.path.join(MODEL_DIR, f"{ticker}_c_xgb_{timestamp}.pkl")
    meta_path = os.path.join(MODEL_DIR, f"{ticker}_c_meta_{timestamp}.pkl")

    with open(xgb_path, "wb") as f:
        pickle.dump(best["model"], f)
    with open(meta_path, "wb") as f:
        pickle.dump({
            "class_map":  best["class_map"],
            "inv_map":    best["inv_map"],
            "best_stage": best_stage,
        }, f)

    logger.info(f"[{ticker}] 모델 저장 완료 ({best_stage})")
    logger.info(f"  XGBoost → {xgb_path}")
    logger.info(f"  Meta    → {meta_path}")
    logger.info(f"=== [{ticker}] Model C 완료 ===")

    return {
        "ticker":       ticker,
        "best_stage":   best_stage,
        "up_precision": best["up_precision"],
        "up_f1":        best["up_f1"],
        "all_results":  {s: {"up_precision": r["up_precision"], "up_f1": r["up_f1"]}
                         for s, r in results.items()},
    }


if __name__ == "__main__":
    final = {}
    for ticker in TICKERS:
        result = train_pipeline_c(ticker)
        if result:
            final[ticker] = result

    logger.info("\n" + "="*60)
    logger.info("전체 Model C 비교 실험 완료")
    logger.info("="*60)
    for ticker, res in final.items():
        logger.info(f"\n[{ticker}] 최종 선택: {res['best_stage']}")
        for stage, metrics in res["all_results"].items():
            marker = " ◀" if stage == res["best_stage"] else ""
            logger.info(f"  {stage}: precision={metrics['up_precision']:.4f} f1={metrics['up_f1']:.4f}{marker}")
