"""
chart_features.py - 규칙 기반 차트패턴 Feature 엔지니어링

DB에서 주가 데이터를 불러와서 차트패턴 기반 feature를 생성.
Model B (XGBoost) 학습에 사용.

생성되는 feature:
- 골든크로스 / 데드크로스 (MA5 vs MA20)
- RSI 과매수 / 과매도
- MACD 시그널 교차
- 볼린저밴드 상단/하단 이탈
- 거래량 급증
"""

import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from settings import DATABASE_URL

logger = logging.getLogger(__name__)

WINDOW_SIZE = 20  # Model A와 동일하게 유지


def load_data(ticker: str) -> pd.DataFrame:
    """DB에서 주가 데이터 로드."""
    engine = create_engine(DATABASE_URL)
    query = text("""
        SELECT date, open, close, volume,
               price_change_pct, ma5, ma20, ma60, rsi, direction
        FROM stock_prices
        WHERE ticker = :ticker
        ORDER BY date ASC
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"ticker": ticker}, parse_dates=["date"])

    df = df.dropna(subset=["ma60"]).reset_index(drop=True)
    logger.info(f"[chart_features] {ticker} 데이터 로드 완료: {len(df)}행")
    return df


def add_chart_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    차트패턴 기반 feature 추가.

    추가되는 컬럼:
    - golden_cross:   MA5가 MA20을 상향 돌파 (0/1)
    - dead_cross:     MA5가 MA20을 하향 돌파 (0/1)
    - rsi_overbought: RSI > 70 (0/1)
    - rsi_oversold:   RSI < 30 (0/1)
    - macd:           MACD 값
    - macd_signal:    MACD 시그널선
    - macd_cross_up:  MACD가 시그널선 상향 돌파 (0/1)
    - macd_cross_down:MACD가 시그널선 하향 돌파 (0/1)
    - bb_upper:       볼린저밴드 상단
    - bb_lower:       볼린저밴드 하단
    - bb_break_up:    볼린저밴드 상단 이탈 (0/1)
    - bb_break_down:  볼린저밴드 하단 이탈 (0/1)
    - volume_surge:   거래량 20일 평균 대비 2배 이상 (0/1)
    - ma5_slope:      MA5 기울기 (상승/하락 추세)
    - price_vs_ma20:  현재가 vs MA20 비율
    """
    df = df.copy()

    # ── 골든크로스 / 데드크로스 ──────────────────────────────
    # 전일 MA5 < MA20 이었다가 오늘 MA5 > MA20 → 골든크로스
    prev_ma5  = df["ma5"].shift(1)
    prev_ma20 = df["ma20"].shift(1)
    df["golden_cross"] = (
        (prev_ma5 <= prev_ma20) & (df["ma5"] > df["ma20"])
    ).astype(int)
    df["dead_cross"] = (
        (prev_ma5 >= prev_ma20) & (df["ma5"] < df["ma20"])
    ).astype(int)

    # ── RSI 과매수 / 과매도 ───────────────────────────────────
    df["rsi_overbought"] = (df["rsi"] > 70).astype(int)
    df["rsi_oversold"]   = (df["rsi"] < 30).astype(int)

    # ── MACD (12일 EMA - 26일 EMA) ────────────────────────────
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    prev_macd   = df["macd"].shift(1)
    prev_signal = df["macd_signal"].shift(1)
    df["macd_cross_up"]   = (
        (prev_macd <= prev_signal) & (df["macd"] > df["macd_signal"])
    ).astype(int)
    df["macd_cross_down"] = (
        (prev_macd >= prev_signal) & (df["macd"] < df["macd_signal"])
    ).astype(int)

    # ── 볼린저밴드 (20일 이동평균 ± 2σ) ─────────────────────
    bb_mid         = df["close"].rolling(20).mean()
    bb_std         = df["close"].rolling(20).std()
    df["bb_upper"] = bb_mid + 2 * bb_std
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_break_up"]   = (df["close"] > df["bb_upper"]).astype(int)
    df["bb_break_down"] = (df["close"] < df["bb_lower"]).astype(int)

    # ── 거래량 급증 (20일 평균 대비 2배) ─────────────────────
    vol_ma20 = df["volume"].rolling(20).mean()
    df["volume_surge"] = (df["volume"] > vol_ma20 * 2).astype(int)

    # ── MA5 기울기 (3일 변화율) ───────────────────────────────
    df["ma5_slope"] = df["ma5"].pct_change(3)

    # ── 현재가 vs MA20 비율 ───────────────────────────────────
    df["price_vs_ma20"] = (df["close"] - df["ma20"]) / df["ma20"]

    return df


# 학습에 사용할 feature 컬럼
CHART_FEATURE_COLS = [
    "golden_cross",
    "dead_cross",
    "rsi_overbought",
    "rsi_oversold",
    "macd",
    "macd_signal",
    "macd_cross_up",
    "macd_cross_down",
    "bb_break_up",
    "bb_break_down",
    "volume_surge",
    "ma5_slope",
    "price_vs_ma20",
    # 기존 지표도 포함
    "rsi",
    "ma5",
    "ma20",
    "ma60",
    "price_change_pct",
]


def make_label(df: pd.DataFrame) -> pd.Series:
    """다음날 방향을 label로 생성. up=2, flat=1, down=0"""
    label_map = {"up": 1, "flat": 0, "down": 0}
    return df["direction"].shift(-1).map(label_map)


def build_chart_dataset(df: pd.DataFrame):
    """
    차트패턴 feature 기반 데이터셋 생성.
    XGBoost용 테이블 형태 (시퀀스 아님).

    Returns:
        X:     (samples, features)
        y:     (samples,)
        dates: (samples,) - 예측 대상 날짜
    """
    df = add_chart_features(df)
    labels = make_label(df)

    # NaN 제거
    df_feat = df[CHART_FEATURE_COLS].copy()
    valid_mask = df_feat.notna().all(axis=1) & labels.notna()

    X      = df_feat[valid_mask].values.astype(np.float32)
    y      = labels[valid_mask].values.astype(np.int64)
    dates  = df["date"][valid_mask].shift(-1).values

    logger.info(f"[chart_features] 데이터셋 생성 완료: X={X.shape}, y={y.shape}")
    logger.info(f"[chart_features] 클래스 분포: down={sum(y==0)} up={sum(y==1)}")
    return X, y, dates
