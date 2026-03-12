import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

from settings import TICKERS, PRICE_PERIOD, PRICE_INTERVAL

logger = logging.getLogger(__name__)

YF_CHART_URL    = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
YF_SUMMARY_URL  = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# 시장 지표 ticker
MARKET_TICKERS = {
    "KOSPI":  "^KS11",
    "KOSDAQ": "^KQ11",
    "NASDAQ": "^IXIC",
    "VIX":    "^VIX",
}


def fetch_price(ticker: str, period: str = PRICE_PERIOD, interval: str = PRICE_INTERVAL) -> list[dict]:
    """
    Yahoo Finance API 직접 호출로 주가 수집.
    기술적 지표 (MA5, MA20, MA60, RSI) 계산 포함.
    충분한 데이터가 없으면 None으로 저장.
    """
    # RSI, MA60 계산을 위해 최소 60일치 데이터 확보
    extended_days = max(_period_to_days(period), 90)

    url = YF_CHART_URL.format(ticker=ticker)
    params = {
        "period1": int((datetime.now() - timedelta(days=extended_days)).timestamp()),
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
        result     = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        ohlcv      = result["indicators"]["quote"][0]
        opens      = ohlcv["open"]
        closes     = ohlcv["close"]
        volumes    = ohlcv["volume"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"[price_fetcher] {ticker} 응답 파싱 실패: {e}")
        return []

    # 기술적 지표 계산을 위한 전체 close 리스트
    close_series = pd.Series([
        round(float(c), 4) for c in closes if c is not None
    ])
    ma5_series  = _calc_ma(close_series, 5)
    ma20_series = _calc_ma(close_series, 20)
    ma60_series = _calc_ma(close_series, 60)
    rsi_series  = _calc_rsi(close_series, 14)

    results = []
    valid_idx = 0  # None 제외한 인덱스 추적

    for ts, o, c, v in zip(timestamps, opens, closes, volumes):
        if o is None or c is None:
            continue
        try:
            date_str         = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            open_price       = round(float(o), 4)
            close_price      = round(float(c), 4)
            volume           = int(v) if v else 0
            price_change     = round(close_price - open_price, 4)
            price_change_pct = round((price_change / open_price) * 100, 4) if open_price else 0.0
            direction        = "up" if price_change > 0 else ("down" if price_change < 0 else "flat")

            # 기술적 지표 (값 없으면 None)
            ma5  = round(float(ma5_series.iloc[valid_idx]), 4)  if valid_idx < len(ma5_series)  and not pd.isna(ma5_series.iloc[valid_idx])  else None
            ma20 = round(float(ma20_series.iloc[valid_idx]), 4) if valid_idx < len(ma20_series) and not pd.isna(ma20_series.iloc[valid_idx]) else None
            ma60 = round(float(ma60_series.iloc[valid_idx]), 4) if valid_idx < len(ma60_series) and not pd.isna(ma60_series.iloc[valid_idx]) else None
            rsi  = round(float(rsi_series.iloc[valid_idx]), 4)  if valid_idx < len(rsi_series)  and not pd.isna(rsi_series.iloc[valid_idx])  else None

            results.append({
                "ticker":           ticker,
                "date":             date_str,
                "open":             open_price,
                "close":            close_price,
                "volume":           volume,
                "price_change":     price_change,
                "price_change_pct": price_change_pct,
                "direction":        direction,
                "ma5":              ma5,
                "ma20":             ma20,
                "ma60":             ma60,
                "rsi":              rsi,
            })
            valid_idx += 1

        except Exception as e:
            logger.warning(f"[price_fetcher] {ticker} {ts} 행 처리 오류: {e}")
            continue

    # PRICE_PERIOD 기간만큼 최신 데이터만 반환
    target_days = _period_to_days(period)
    results = results[-target_days:] if len(results) > target_days else results

    logger.info(f"[price_fetcher] {ticker} {len(results)}개 수집 완료")
    return results


def fetch_fundamental(ticker: str) -> dict | None:
    """
    Yahoo Finance quoteSummary API로 펀더멘털 데이터 수집.
    시가총액(market_cap), PER, PBR 반환.
    """
    url = YF_SUMMARY_URL.format(ticker=ticker)
    params = {"modules": "summaryDetail,defaultKeyStatistics"}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"[price_fetcher] {ticker} 펀더멘털 요청 실패: {e}")
        return None

    try:
        summary = data["quoteSummary"]["result"][0]
        detail  = summary.get("summaryDetail", {})
        stats   = summary.get("defaultKeyStatistics", {})

        market_cap = detail.get("marketCap", {}).get("raw")
        per        = detail.get("trailingPE", {}).get("raw")
        pbr        = stats.get("priceToBook", {}).get("raw")

        return {
            "ticker":     ticker,
            "date":       datetime.now().strftime("%Y-%m-%d"),
            "market_cap": round(float(market_cap), 2) if market_cap else None,
            "per":        round(float(per), 4)        if per        else None,
            "pbr":        round(float(pbr), 4)        if pbr        else None,
        }
    except Exception as e:
        logger.warning(f"[price_fetcher] {ticker} 펀더멘털 파싱 실패: {e}")
        return None


def fetch_market_indicators(period: str = PRICE_PERIOD) -> list[dict]:
    """
    KOSPI, KOSDAQ, 나스닥, VIX 시장 지표 수집.
    """
    results = []
    for name, ticker in MARKET_TICKERS.items():
        prices = fetch_price(ticker, period=period)
        for p in prices:
            results.append({
                "ticker":     ticker,
                "date":       p["date"],
                "close":      p["close"],
                "change_pct": p["price_change_pct"],
            })
    logger.info(f"[price_fetcher] 시장 지표 {len(results)}개 수집 완료")
    return results


def fetch_all_prices() -> dict[str, list[dict]]:
    return {ticker: fetch_price(ticker) for ticker in TICKERS}


# ── 기술적 지표 계산 ───────────────────────────────────────────

def _calc_ma(series: pd.Series, window: int) -> pd.Series:
    """이동평균선 계산"""
    return series.rolling(window=window).mean()


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI (Relative Strength Index) 계산
    0 ~ 100 범위, 70 이상 과매수 / 30 이하 과매도
    """
    delta  = series.diff()
    gain   = delta.clip(lower=0)
    loss   = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _period_to_days(period: str) -> int:
    """'5d' → 5, '1mo' → 30, '3mo' → 90"""
    try:
        if period.endswith("mo"):
            return int(period[:-2]) * 30
        elif period.endswith("d"):
            return int(period[:-1])
    except ValueError:
        pass
    return 7
