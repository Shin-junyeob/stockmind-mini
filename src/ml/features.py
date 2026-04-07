"""
features.py - Feature 엔지니어링

DB에서 주가 + 시장 지표 데이터를 불러와서
LSTM용 시퀀스와 XGBoost용 테이블 형태로 변환.
"""

import logging
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from settings import DATABASE_URL

logger = logging.getLogger(__name__)

# LSTM 입력 윈도우 크기 (최근 N일치 시퀀스)
WINDOW_SIZE = 20

# 사용할 feature 컬럼
PRICE_FEATURES = [
    "close",
    "volume",
    "price_change_pct",
    "ma5",
    "ma20",
    "ma60",
    "rsi",
]

MARKET_FEATURES = [
    "ks11_close",    # KOSPI
    "ixic_close",    # 나스닥
    "vix_close",     # VIX
]

ALL_FEATURES = PRICE_FEATURES + MARKET_FEATURES


def load_data(ticker: str) -> pd.DataFrame:
    """
    DB에서 주가 + 시장 지표를 불러와서 하나의 DataFrame으로 합침.
    MA60이 None인 초기 행은 제거.
    """
    engine = create_engine(DATABASE_URL)

    # 주가 데이터
    price_query = text("""
        SELECT date, close, volume, price_change_pct,
               ma5, ma20, ma60, rsi, direction
        FROM stock_prices
        WHERE ticker = :ticker
        ORDER BY date ASC
    """)

    # 시장 지표 (KOSPI, 나스닥, VIX)
    market_query = text("""
        SELECT date,
               MAX(CASE WHEN ticker = '^KS11' THEN close END) AS ks11_close,
               MAX(CASE WHEN ticker = '^IXIC' THEN close END) AS ixic_close,
               MAX(CASE WHEN ticker = '^VIX'  THEN close END) AS vix_close
        FROM market_indicators
        GROUP BY date
        ORDER BY date ASC
    """)

    with engine.connect() as conn:
        price_df  = pd.read_sql(price_query,  conn, params={"ticker": ticker}, parse_dates=["date"])
        market_df = pd.read_sql(market_query, conn, parse_dates=["date"])

    # 날짜 기준으로 병합
    df = price_df.merge(market_df, on="date", how="left")

    # MA60이 None인 초기 행 제거 (충분한 데이터 없는 구간)
    df = df.dropna(subset=["ma60"]).reset_index(drop=True)

    # 시장 지표 NaN은 forward fill로 처리
    df[MARKET_FEATURES] = df[MARKET_FEATURES].ffill()

    logger.info(f"[features] {ticker} 데이터 로드 완료: {len(df)}행")
    return df


def make_label(df: pd.DataFrame) -> pd.Series:
    """
    다음날 방향을 label로 생성.
    up=2, flat=1, down=0
    """
    label_map = {"up": 1, "flat": 0, "down": 0}
    # 다음날 direction을 현재 행의 label로 사용
    labels = df["direction"].shift(-1).map(label_map)
    return labels


def build_sequences(df: pd.DataFrame, window: int = WINDOW_SIZE):
    """
    LSTM용 3D 시퀀스 생성.

    반환:
    X_seq: (samples, window, features) - LSTM 입력
    X_tab: (samples, features)          - XGBoost 입력 (마지막 날 feature)
    y:     (samples,)                   - label
    dates: (samples,)                   - 예측 대상 날짜
    """
    feature_cols = ALL_FEATURES
    df_feat = df[feature_cols].copy()

    labels = make_label(df)

    X_seq, X_tab, y, dates = [], [], [], []

    for i in range(window, len(df) - 1):
        # 유효한 label만 사용
        if pd.isna(labels.iloc[i]):
            continue

        seq = df_feat.iloc[i - window:i].values   # (window, features)
        tab = df_feat.iloc[i].values               # (features,)
        label = int(labels.iloc[i])
        date  = df["date"].iloc[i + 1]               # 예측 대상 날짜

        X_seq.append(seq)
        X_tab.append(tab)
        y.append(label)
        dates.append(date)

    X_seq = np.array(X_seq, dtype=np.float32)
    X_tab = np.array(X_tab, dtype=np.float32)
    y     = np.array(y, dtype=np.int64)

    logger.info(f"[features] 시퀀스 생성 완료: X_seq={X_seq.shape}, X_tab={X_tab.shape}, y={y.shape}")
    return X_seq, X_tab, y, dates
