"""
eval_compare.py - 신규 모델과 기존 모델 성능 비교 후 교체 여부 결정

흐름:
  1. models/{ticker}_perf_*.json 에서 최신 2개 로드
  2. 신규 Ensemble up_f1 >= 기존 up_f1 + MIN_IMPROVEMENT 이면 신규 유지
  3. 조건 미충족 시 오늘 날짜 모델 파일 전부 삭제 (기존 모델로 자동 롤백)

실행: PYTHONPATH=src python src/ml/eval_compare.py
"""

import glob
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from settings import TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

MODEL_DIR       = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
MIN_IMPROVEMENT = 0.02   # 신규 모델이 기존보다 up_f1 +2% 이상이어야 교체


# ── 모델 파일 suffix 패턴 ─────────────────────────────────────
# predictor.py가 glob sorted()[-1]로 최신 파일을 선택하므로
# 오늘 날짜 파일을 삭제하면 자동으로 이전 모델로 롤백됨.
MODEL_PATTERNS = [
    "{ticker}_lstm_{date}.pt",
    "{ticker}_xgb_{date}.pkl",
    "{ticker}_scaler_{date}.pkl",
    "{ticker}_meta_{date}.pkl",
    "{ticker}_b_xgb_{date}.pkl",
    "{ticker}_b_meta_{date}.pkl",
    "{ticker}_c_xgb_{date}.pkl",
    "{ticker}_c_meta_{date}.pkl",
    "{ticker}_ensemble_xgb_{date}.pkl",
    "{ticker}_ensemble_meta_{date}.pkl",
    "{ticker}_threshold.json",
]


def load_latest_two_perfs(ticker: str) -> tuple[dict | None, dict | None]:
    """
    가장 최신 perf JSON 2개 반환 (newest, previous).
    파일이 1개면 (newest, None), 없으면 (None, None).
    """
    pattern = os.path.join(MODEL_DIR, f"{ticker}_perf_*.json")
    files   = sorted(glob.glob(pattern))

    if len(files) == 0:
        return None, None
    if len(files) == 1:
        with open(files[-1]) as f:
            return json.load(f), None

    with open(files[-1]) as f:
        newest = json.load(f)
    with open(files[-2]) as f:
        previous = json.load(f)
    return newest, previous


def delete_today_models(ticker: str, today: str) -> list[str]:
    """오늘 날짜로 저장된 모델 파일 삭제. 삭제된 파일 목록 반환."""
    deleted = []
    for pattern in MODEL_PATTERNS:
        path = os.path.join(MODEL_DIR, pattern.format(ticker=ticker, date=today))
        if os.path.exists(path):
            os.remove(path)
            deleted.append(os.path.basename(path))
    return deleted


def compare_and_maybe_rollback(ticker: str, today: str) -> dict:
    """
    신규 모델 성능 비교 후 롤백 여부 결정.
    반환: {"kept": bool, "new_f1": float, "old_f1": float, "reason": str}
    """
    newest, previous = load_latest_two_perfs(ticker)

    # perf 파일이 없거나 1개뿐이면 비교 대상 없음 → 신규 유지
    if newest is None:
        return {"kept": True, "new_f1": 0.0, "old_f1": 0.0, "reason": "perf 파일 없음 — 신규 유지"}

    if previous is None:
        new_f1 = newest.get("Ensemble", {}).get("up_f1", 0.0)
        return {"kept": True, "new_f1": new_f1, "old_f1": 0.0, "reason": "최초 학습 — 비교 대상 없음, 신규 유지"}

    new_f1 = newest.get("Ensemble", {}).get("up_f1", 0.0)
    old_f1 = previous.get("Ensemble", {}).get("up_f1", 0.0)
    delta  = new_f1 - old_f1

    if delta >= MIN_IMPROVEMENT:
        reason = f"up_f1 {old_f1:.4f} → {new_f1:.4f} (+{delta:.4f}) ≥ {MIN_IMPROVEMENT} — 신규 채택"
        logger.info(f"[{ticker}] ✅ {reason}")
        return {"kept": True, "new_f1": new_f1, "old_f1": old_f1, "reason": reason}
    else:
        reason = f"up_f1 {old_f1:.4f} → {new_f1:.4f} ({delta:+.4f}) < {MIN_IMPROVEMENT} — 롤백"
        logger.warning(f"[{ticker}] ⚠️  {reason}")
        deleted = delete_today_models(ticker, today)
        logger.warning(f"[{ticker}] 삭제된 파일: {deleted}")
        return {"kept": False, "new_f1": new_f1, "old_f1": old_f1, "reason": reason}


def run_eval_compare(tickers: list[str] = TICKERS) -> None:
    today = datetime.now().strftime("%Y%m%d")
    logger.info(f"=== eval_compare 시작 | date={today} | tickers={tickers} ===")

    summary = {}
    for ticker in tickers:
        result = compare_and_maybe_rollback(ticker, today)
        summary[ticker] = result

    logger.info("\n" + "=" * 60)
    logger.info("eval_compare 완료 — 결과 요약")
    logger.info("=" * 60)
    for ticker, res in summary.items():
        status = "✅ 채택" if res["kept"] else "⚠️  롤백"
        logger.info(
            f"{ticker:<12} {status}  "
            f"old_f1={res['old_f1']:.4f}  new_f1={res['new_f1']:.4f}  "
            f"| {res['reason']}"
        )


if __name__ == "__main__":
    run_eval_compare()
