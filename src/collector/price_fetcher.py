import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

from settings import TICKERS, PRICE_PERIOD, PRICE_INTERVAL

logger = logging.getLogger(__name__)

YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_price(ticker: str, period: str = PRICE_PERIOD, interval: str = PRICE_INTERVAL) -> list[dict]:
    """
    yfinance 없이 Yahoo Finance API를 직접 호출.
    Docker 환경에서 yfinance 내부 파싱 이슈를 우회.
    """
    url = YF_CHART_URL.format(ticker=ticker)
    params = {
        "period1": int((datetime.now() - timedelta(days=_period_to_days(period))).timestamp()),
        "period2": int(datetime.now().timestamp()),
        "interval": interval,
        "includePrePost": "false",
    }

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[price_fetcher] {ticker} 요청 실패: {e}")
        return []

    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv = result["indicators"]["quote"][0]
        opens   = ohlcv["open"]
        closes  = ohlcv["close"]
        volumes = ohlcv["volume"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"[price_fetcher] {ticker} 응답 파싱 실패: {e}")
        return []

    results = []
    for ts, o, c, v in zip(timestamps, opens, closes, volumes):
        if o is None or c is None:
            continue
        try:
            date_str     = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            open_price   = round(float(o), 4)
            close_price  = round(float(c), 4)
            volume       = int(v) if v else 0
            price_change     = round(close_price - open_price, 4)
            price_change_pct = round((price_change / open_price) * 100, 4) if open_price else 0.0
            direction = "up" if price_change > 0 else ("down" if price_change < 0 else "flat")

            results.append({
                "ticker":           ticker,
                "date":             date_str,
                "open":             open_price,
                "close":            close_price,
                "volume":           volume,
                "price_change":     price_change,
                "price_change_pct": price_change_pct,
                "direction":        direction,
            })
        except Exception as e:
            logger.warning(f"[price_fetcher] {ticker} {ts} 행 처리 오류: {e}")
            continue

    logger.info(f"[price_fetcher] {ticker} {len(results)}개 수집 완료")
    return results


def _period_to_days(period: str) -> int:
    """'5d' → 5, '1mo' → 30, '3mo' → 90"""
    if period.endswith("d"):
        return int(period[:-1])
    elif period.endswith("mo"):
        return int(period[:-2]) * 30
    return 7


def fetch_all_prices() -> dict[str, list[dict]]:
    return {ticker: fetch_price(ticker) for ticker in TICKERS}
