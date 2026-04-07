"""
backfill_fear_greed.py - CNN Fear & Greed Index 과거 데이터 수집

용도: Model C 학습에 필요한 2021년~현재 Fear & Greed Index 수집
실행: PYTHONPATH=src python scripts/backfill_fear_greed.py

주의:
- 1회만 실행하면 됨 (중복 데이터는 upsert로 자동 처리)
- CNN 비공식 API 사용 (2021-01-01 이후 데이터 제공)
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from collector.fear_greed_fetcher import fetch_fear_greed
from db.writer import init_db, upsert_fear_greed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_backfill() -> None:
    logger.info("=== Fear & Greed Index backfill 시작 ===")

    init_db()

    data = fetch_fear_greed(from_date="2021-01-01")
    if data:
        saved = upsert_fear_greed(data)
        logger.info(f"저장 완료: {saved}건 ({data[0]['date']} ~ {data[-1]['date']})")
    else:
        logger.warning("데이터 없음")

    logger.info("=== Fear & Greed Index backfill 완료 ===")


if __name__ == "__main__":
    run_backfill()
