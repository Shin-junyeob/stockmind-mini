"""
train.py - ML 학습 오케스트레이터

실행: PYTHONPATH=src python src/ml/train.py

전체 흐름:
  Model A (LSTM+XGBoost)  →
  Model B (차트패턴 XGBoost) →
  Model C (감성 XGBoost)   →
  Ensemble (Meta XGBoost)
"""

import json
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from ml.train_a import train_pipeline
from ml.train_b import train_pipeline_b
from ml.train_c import train_pipeline_c
from ml.train_ensemble import train_ensemble
from settings import TICKERS

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_training(tickers: list[str] = TICKERS) -> None:
    """
    전체 ML 학습 파이프라인 실행.
    각 단계 실패 시 해당 ticker만 스킵하고 계속 진행.
    """
    logger.info(f"=== ML 학습 시작 | tickers={tickers} ===")

    results = {ticker: {} for ticker in tickers}

    # ── Model A ───────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("[ 1/4 ] Model A 학습 (LSTM + XGBoost)")
    logger.info("=" * 60)
    for ticker in tickers:
        try:
            res = train_pipeline(ticker)
            if res:
                results[ticker]["A"] = res
        except Exception as e:
            logger.error(f"[{ticker}] Model A 실패: {e}")

    # ── Model B ───────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("[ 2/4 ] Model B 학습 (차트패턴 XGBoost)")
    logger.info("=" * 60)
    for ticker in tickers:
        try:
            res = train_pipeline_b(ticker)
            if res:
                results[ticker]["B"] = res
        except Exception as e:
            logger.error(f"[{ticker}] Model B 실패: {e}")

    # ── Model C ───────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("[ 3/4 ] Model C 학습 (감성 XGBoost)")
    logger.info("=" * 60)
    for ticker in tickers:
        try:
            res = train_pipeline_c(ticker)
            if res:
                results[ticker]["C"] = res
        except Exception as e:
            logger.error(f"[{ticker}] Model C 실패: {e}")

    # ── Ensemble ──────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("[ 4/4 ] Ensemble 학습 (Meta XGBoost)")
    logger.info("=" * 60)
    for ticker in tickers:
        try:
            res = train_ensemble(ticker)
            if res:
                results[ticker]["Ensemble"] = res
        except Exception as e:
            logger.error(f"[{ticker}] Ensemble 실패: {e}")

    # ── 최종 요약 + perf JSON 저장 ───────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ML 학습 전체 완료 — 결과 요약")
    logger.info("=" * 60)
    logger.info(f"{'Ticker':<12} {'Model':<10} {'up_precision':>14} {'up_f1':>8}")
    logger.info("-" * 48)
    for ticker, models in results.items():
        for model_name, res in models.items():
            logger.info(
                f"{ticker:<12} {model_name:<10} "
                f"{res.get('up_precision', 0):.4f}         "
                f"{res.get('up_f1', 0):.4f}"
            )

    # 학습 결과를 perf JSON으로 저장 (eval_compare.py에서 사용)
    os.makedirs(MODEL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    for ticker, models in results.items():
        if not models:
            continue
        perf = {
            model_name: {
                "up_f1":       res.get("up_f1", 0.0),
                "up_precision": res.get("up_precision", 0.0),
            }
            for model_name, res in models.items()
        }
        perf_path = os.path.join(MODEL_DIR, f"{ticker}_perf_{timestamp}.json")
        with open(perf_path, "w") as f:
            json.dump(perf, f, indent=2)
        logger.info(f"[{ticker}] perf 저장: {perf_path}")


if __name__ == "__main__":
    run_training()
