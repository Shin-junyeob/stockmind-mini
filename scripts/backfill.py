"""
backfill.py - 1회성 과거 데이터 수집 스크립트

용도: 예측모델 학습에 필요한 과거 1년치 주가 + 시장 지표 데이터 수집
실행: PYTHONPATH=src python scripts/backfill.py

주의:
- 1회만 실행하면 됨 (중복 데이터는 upsert로 자동 처리)
- 매일 자동 수집(cron)과 별개로 동작
- PRICE_PERIOD 환경변수와 무관하게 항상 1y로 수집
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from settings import TICKERS
from collector.price_fetcher import fetch_price, fetch_market_indicators
from db.writer import init_db, upsert_stock_prices, upsert_market_indicators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

BACKFILL_PERIOD   = "1y"   # 1년치 과거 데이터
BACKFILL_INTERVAL = "1d"   # 일봉


def run_backfill(tickers: list[str] = TICKERS) -> None:
    """
    과거 1년치 주가 + 시장 지표 수집 및 DB 저장.
    기술적 지표 (MA5, MA20, MA60, RSI) 자동 계산 포함.
    """
    logger.info("=== backfill 시작 ===")
    logger.info(f"수집 기간: {BACKFILL_PERIOD} / 인터벌: {BACKFILL_INTERVAL}")
    logger.info(f"대상 ticker: {tickers}")

    init_db()

    # ── 시장 지표 수집 (KOSPI, KOSDAQ, 나스닥, VIX) ──────────
    logger.info("시장 지표 수집 중... (KOSPI, KOSDAQ, 나스닥, VIX)")
    market_data = fetch_market_indicators(period=BACKFILL_PERIOD)
    if market_data:
        saved = upsert_market_indicators(market_data)
        logger.info(f"시장 지표 저장 완료: {saved}건")
    else:
        logger.warning("시장 지표 데이터 없음, 스킵")

    # ── 주가 수집 (ticker별) ──────────────────────────────────
    for ticker in tickers:
        logger.info(f"--- [{ticker}] 주가 수집 중... ---")
        price_data = fetch_price(
            ticker,
            period=BACKFILL_PERIOD,
            interval=BACKFILL_INTERVAL,
        )
        if price_data:
            saved = upsert_stock_prices(price_data)
            logger.info(f"[{ticker}] 저장 완료: {saved}건")

            # MA60 계산 가능 여부 확인
            ma60_count = sum(1 for p in price_data if p.get("ma60") is not None)
            rsi_count  = sum(1 for p in price_data if p.get("rsi")  is not None)
            logger.info(f"[{ticker}] MA60 계산 가능: {ma60_count}건 / RSI 계산 가능: {rsi_count}건")
        else:
            logger.warning(f"[{ticker}] 데이터 없음, 스킵")

    logger.info("=== backfill 완료 ===")
    logger.info("이제 매일 cron으로 5d씩 자동 수집됩니다.")


if __name__ == "__main__":
    run_backfill()
