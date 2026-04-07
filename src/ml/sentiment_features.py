"""
sentiment_features.py - Model C Feature 엔지니어링 (감성 기반)

3가지 접근법 지원:
  stage2: Fear & Greed Index만 사용 (5년치)
  stage3: Fear & Greed + VIX 결합 (5년치)
  stage4: 뉴스 감성 분석 결과만 사용 (2개월치)
"""

import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from settings import DATABASE_URL

logger = logging.getLogger(__name__)


# ── 공통 유틸 ─────────────────────────────────────────────────

def _make_label(df: pd.DataFrame) -> pd.Series:
    """다음날 방향을 label로 생성. up=1, down/flat=0"""
    return df["direction"].shift(-1).map({"up": 1, "flat": 0, "down": 0})


def _to_dataset(df: pd.DataFrame, feature_cols: list[str]):
    """feature_cols 기준으로 X, y, dates 반환."""
    labels    = _make_label(df)
    df_feat   = df[feature_cols].copy()
    valid     = df_feat.notna().all(axis=1) & labels.notna()

    X     = df_feat[valid].values.astype(np.float32)
    y     = labels[valid].values.astype(np.int64)
    dates = df["date"][valid].shift(-1).values

    logger.info(f"  데이터셋: X={X.shape} | down={sum(y==0)} up={sum(y==1)}")
    return X, y, dates


# ── 데이터 로드 ───────────────────────────────────────────────

def _load_base(ticker: str) -> pd.DataFrame:
    """주가 방향 + Fear&Greed + VIX 병합."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        price_df = pd.read_sql(text("""
            SELECT date, direction FROM stock_prices
            WHERE ticker = :ticker ORDER BY date ASC
        """), conn, params={"ticker": ticker}, parse_dates=["date"])

        fg_df = pd.read_sql(text("""
            SELECT date, score AS fg_score FROM fear_greed ORDER BY date ASC
        """), conn, parse_dates=["date"])

        vix_df = pd.read_sql(text("""
            SELECT date, MAX(CASE WHEN ticker = '^VIX' THEN close END) AS vix
            FROM market_indicators GROUP BY date ORDER BY date ASC
        """), conn, parse_dates=["date"])

    df = price_df.merge(fg_df, on="date", how="left")
    df = df.merge(vix_df, on="date", how="left")
    df["fg_score"] = df["fg_score"].ffill()
    df["vix"]      = df["vix"].ffill()
    return df


def _load_news(ticker: str) -> pd.DataFrame:
    """주가 방향 + 일별 뉴스 감성 집계."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        price_df = pd.read_sql(text("""
            SELECT date, direction FROM stock_prices
            WHERE ticker = :ticker ORDER BY date ASC
        """), conn, params={"ticker": ticker}, parse_dates=["date"])

        news_df = pd.read_sql(text("""
            SELECT date,
                   AVG(sentiment_score)                                       AS news_avg_score,
                   COUNT(*)                                                    AS news_count,
                   SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) AS pos_count,
                   SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS neg_count
            FROM news_articles
            WHERE ticker = :ticker
            GROUP BY date ORDER BY date ASC
        """), conn, params={"ticker": ticker}, parse_dates=["date"])

    df = price_df.merge(news_df, on="date", how="left")
    return df


# ── Stage 2: Fear & Greed만 ──────────────────────────────────

STAGE2_COLS = [
    "fg_score",
    "fg_extreme_fear",
    "fg_fear",
    "fg_greed",
    "fg_extreme_greed",
    "fg_ma5",
    "fg_slope",
]


def build_stage2_dataset(ticker: str):
    """Fear & Greed Index만 사용 (5년치)."""
    logger.info(f"[stage2] {ticker} Fear & Greed only")
    df = _load_base(ticker)
    df = df.dropna(subset=["fg_score"]).reset_index(drop=True)

    df["fg_extreme_fear"]  = (df["fg_score"] < 25).astype(int)
    df["fg_fear"]          = ((df["fg_score"] >= 25) & (df["fg_score"] < 45)).astype(int)
    df["fg_greed"]         = ((df["fg_score"] > 55) & (df["fg_score"] <= 75)).astype(int)
    df["fg_extreme_greed"] = (df["fg_score"] > 75).astype(int)
    df["fg_ma5"]           = df["fg_score"].rolling(5).mean()
    df["fg_slope"]         = df["fg_score"].pct_change(5)

    return _to_dataset(df, STAGE2_COLS)


# ── Stage 3: Fear & Greed + VIX ──────────────────────────────

STAGE3_COLS = [
    "fg_score",
    "fg_extreme_fear",
    "fg_fear",
    "fg_greed",
    "fg_extreme_greed",
    "fg_ma5",
    "fg_slope",
    "vix",
    "vix_high",
    "vix_slope",
    "fg_vix_diverge",
]


def build_stage3_dataset(ticker: str):
    """Fear & Greed + VIX 결합 (5년치)."""
    logger.info(f"[stage3] {ticker} Fear & Greed + VIX")
    df = _load_base(ticker)
    df = df.dropna(subset=["fg_score", "vix"]).reset_index(drop=True)

    df["fg_extreme_fear"]  = (df["fg_score"] < 25).astype(int)
    df["fg_fear"]          = ((df["fg_score"] >= 25) & (df["fg_score"] < 45)).astype(int)
    df["fg_greed"]         = ((df["fg_score"] > 55) & (df["fg_score"] <= 75)).astype(int)
    df["fg_extreme_greed"] = (df["fg_score"] > 75).astype(int)
    df["fg_ma5"]           = df["fg_score"].rolling(5).mean()
    df["fg_slope"]         = df["fg_score"].pct_change(5)
    df["vix_high"]         = (df["vix"] > 30).astype(int)
    df["vix_slope"]        = df["vix"].pct_change(5)
    df["fg_vix_diverge"]   = ((df["fg_slope"] > 0) & (df["vix_slope"] > 0)).astype(int)

    return _to_dataset(df, STAGE3_COLS)


# ── Stage 4: 뉴스 감성만 ─────────────────────────────────────

STAGE4_COLS = [
    "news_avg_score",
    "news_count",
    "pos_ratio",
    "neg_ratio",
    "score_ma3",
    "score_ma7",
    "score_slope3",
]


def build_stage4_dataset(ticker: str):
    """뉴스 감성 분석 결과만 사용 (약 2개월치)."""
    logger.info(f"[stage4] {ticker} 뉴스 감성만")
    df = _load_news(ticker)

    # 뉴스 없는 날 → 0으로 처리
    df["news_avg_score"] = df["news_avg_score"].fillna(0.0)
    df["news_count"]     = df["news_count"].fillna(0).astype(int)
    df["pos_count"]      = df["pos_count"].fillna(0)
    df["neg_count"]      = df["neg_count"].fillna(0)

    total = df["news_count"].replace(0, float("nan"))
    df["pos_ratio"]    = df["pos_count"] / total
    df["neg_ratio"]    = df["neg_count"] / total
    df["score_ma3"]    = df["news_avg_score"].rolling(3).mean()
    df["score_ma7"]    = df["news_avg_score"].rolling(7).mean()
    df["score_slope3"] = df["news_avg_score"].pct_change(3)

    # 뉴스가 하나라도 있는 날만 유효
    df = df[df["news_count"] > 0].reset_index(drop=True)
    logger.info(f"  뉴스 보유 날짜: {len(df)}일")

    return _to_dataset(df, STAGE4_COLS)
