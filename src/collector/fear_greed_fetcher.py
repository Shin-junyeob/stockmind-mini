"""
fear_greed_fetcher.py - CNN Fear & Greed Index 수집

CNN 비공식 API로 일별 Fear & Greed Index를 수집.
2021년 초부터 현재까지 약 5년치 데이터 제공.

Fear & Greed Index 구성 요소:
- Market Momentum (S&P500 vs 125-day MA)
- Stock Price Strength (52-week highs vs lows)
- Stock Price Breadth (advancing vs declining volume)
- Put & Call Options (put/call ratio)
- Market Volatility (VIX vs 50-day MA)
- Junk Bond Demand (high yield vs investment grade spread)
- Safe Haven Demand (stocks vs bonds return)
"""

import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

FG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{from_date}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://edition.cnn.com/markets/fear-and-greed",
}

FG_START_DATE = "2021-01-01"  # API가 제공하는 최초 날짜


def fetch_fear_greed(from_date: str = FG_START_DATE) -> list[dict]:
    """
    CNN Fear & Greed Index 수집.

    Args:
        from_date: 수집 시작일 (YYYY-MM-DD), 기본값 2021-01-01

    Returns:
        [{"date": "YYYY-MM-DD", "score": float, "rating": str}, ...]
        rating: "extreme fear" | "fear" | "neutral" | "greed" | "extreme greed"
    """
    url = FG_URL.format(from_date=from_date)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[fear_greed] 요청 실패: {e}")
        return []

    try:
        raw_points = data["fear_and_greed_historical"]["data"]
    except (KeyError, TypeError) as e:
        logger.warning(f"[fear_greed] 응답 파싱 실패: {e}")
        return []

    results = []
    for pt in raw_points:
        try:
            ts       = pt["x"] / 1000  # ms → seconds
            score    = round(float(pt["y"]), 2)
            rating   = pt.get("rating", "")
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            results.append({
                "date":   date_str,
                "score":  score,
                "rating": rating,
            })
        except Exception as e:
            logger.warning(f"[fear_greed] 행 처리 오류: {e} → {pt}")
            continue

    if results:
        logger.info(
            f"[fear_greed] {len(results)}건 수집 완료 "
            f"({results[0]['date']} ~ {results[-1]['date']})"
        )
    return results
