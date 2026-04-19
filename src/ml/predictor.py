"""
predictor.py - 앙상블 예측 모듈

저장된 Model A/B/C + Ensemble 모델을 로드하고,
DB의 최신 데이터로 내일 주가 방향을 예측.
API에서 호출됨.
"""

import glob
import logging
import os
import pickle

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

from ml.features import load_data, build_sequences
from ml.chart_features import load_data as load_data_b, build_chart_dataset
from ml.sentiment_features import build_stage2_dataset, build_stage3_dataset, build_stage4_dataset
from ml.lstm_model import LSTMClassifier, predict_proba_lstm
from ml.xgb_model import build_xgb_features, predict_xgb
from ml.tune_threshold import load_threshold

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')

PRICE_FEATURES = [
    "close", "volume", "price_change_pct",
    "ma5", "ma20", "ma60", "rsi",
    "ks11_close", "ixic_close", "vix_close",
]
WINDOW_SIZE = 20


def _find_latest(pattern: str) -> str:
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"모델 파일 없음: {pattern}")
    return sorted(files)[-1]


def _up_proba(proba: np.ndarray) -> float:
    """proba 배열에서 up(class 1) 확률 추출."""
    if proba.shape[1] >= 2:
        return float(proba[-1, 1])
    return float(proba[-1, 0])


class EnsemblePredictor:
    """
    ticker별 앙상블 예측기.
    모델은 최초 1회 로드 후 캐싱.
    """

    def __init__(self, ticker: str):
        self.ticker    = ticker
        self.threshold = load_threshold(ticker)
        self._load_models()
        logger.info(f"[{self.ticker}] 적용 threshold={self.threshold}")

    def _load_models(self):
        logger.info(f"[{self.ticker}] 모델 로드 시작")

        # Model A
        self.lstm_model, self.scaler, self.xgb_a, self.meta_a = self._load_model_a()

        # Model B
        self.xgb_b = self._load_xgb(f"{self.ticker}_b_xgb_*.pkl")

        # Model C
        self.xgb_c, self.meta_c = self._load_model_c()

        # Ensemble
        self.xgb_ensemble = self._load_xgb(f"{self.ticker}_ensemble_xgb_*.pkl")

        logger.info(f"[{self.ticker}] 모델 로드 완료")

    def _load_model_a(self):
        lstm_path   = _find_latest(os.path.join(MODEL_DIR, f"{self.ticker}_lstm_*.pt"))
        xgb_path    = _find_latest(os.path.join(MODEL_DIR, f"{self.ticker}_xgb_*.pkl"))
        scaler_path = _find_latest(os.path.join(MODEL_DIR, f"{self.ticker}_scaler_*.pkl"))
        meta_path   = _find_latest(os.path.join(MODEL_DIR, f"{self.ticker}_meta_*.pkl"))

        with open(scaler_path, "rb") as f:
            scaler: StandardScaler = pickle.load(f)
        with open(xgb_path, "rb") as f:
            xgb_model = pickle.load(f)
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)

        n_classes = meta["n_classes"]
        lstm_model = LSTMClassifier(input_size=len(PRICE_FEATURES), num_classes=n_classes)
        lstm_model.load_state_dict(
            torch.load(lstm_path, map_location="cpu", weights_only=True)
        )
        lstm_model.eval()

        return lstm_model, scaler, xgb_model, meta

    def _load_xgb(self, pattern: str):
        path = _find_latest(os.path.join(MODEL_DIR, pattern))
        with open(path, "rb") as f:
            return pickle.load(f)

    def _load_model_c(self):
        xgb_path  = _find_latest(os.path.join(MODEL_DIR, f"{self.ticker}_c_xgb_*.pkl"))
        meta_path = _find_latest(os.path.join(MODEL_DIR, f"{self.ticker}_c_meta_*.pkl"))
        with open(xgb_path, "rb") as f:
            xgb_model = pickle.load(f)
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)
        return xgb_model, meta

    # ── 개별 모델 예측 ─────────────────────────────────────────

    def _proba_a(self) -> float:
        df = load_data(self.ticker)
        X_seq, X_tab, _, dates = build_sequences(df)

        n = len(PRICE_FEATURES)
        X_seq_s = self.scaler.transform(
            X_seq.reshape(-1, n)
        ).reshape(-1, WINDOW_SIZE, n).astype(np.float32)
        X_tab_s = self.scaler.transform(X_tab).astype(np.float32)

        lstm_proba = predict_proba_lstm(self.lstm_model, X_seq_s)
        X_combined = build_xgb_features(lstm_proba, X_tab_s)
        _, proba = predict_xgb(self.xgb_a, X_combined)

        last_date = dates[-1]
        return float(proba[-1, 1]) if proba.shape[1] >= 2 else float(proba[-1, 0]), last_date

    def _proba_b(self) -> float:
        df = load_data_b(self.ticker)
        X, _, dates = build_chart_dataset(df)
        _, proba = predict_xgb(self.xgb_b, X)
        return float(proba[-1, 1]) if proba.shape[1] >= 2 else float(proba[-1, 0])

    def _proba_c(self) -> float:
        best_stage = self.meta_c["best_stage"]
        stage_fn = {
            "stage2": build_stage2_dataset,
            "stage3": build_stage3_dataset,
            "stage4": build_stage4_dataset,
        }
        X, _, _ = stage_fn[best_stage](self.ticker)
        _, proba = predict_xgb(self.xgb_c, X)
        return float(proba[-1, 1]) if proba.shape[1] >= 2 else float(proba[-1, 0])

    # ── 앙상블 예측 ────────────────────────────────────────────

    def predict(self) -> dict:
        """
        최신 데이터로 내일 주가 방향 예측.

        Returns:
            {
                "ticker": str,
                "prediction_date": str,   # 예측 대상 날짜 (내일)
                "based_on_date": str,     # 사용한 최신 데이터 날짜
                "direction": str,         # "up" | "down"
                "up_probability": float,  # 앙상블 up 확률
                "model_probabilities": {
                    "model_a": float,
                    "model_b": float,
                    "model_c": float,
                }
            }
        """
        logger.info(f"[{self.ticker}] 예측 시작")

        proba_a, based_on_date = self._proba_a()
        proba_b = self._proba_b()
        proba_c = self._proba_c()

        X_meta = np.array([[proba_a, proba_b, proba_c]], dtype=np.float32)
        preds, proba_ens = predict_xgb(self.xgb_ensemble, X_meta)

        up_prob   = float(proba_ens[0, 1]) if proba_ens.shape[1] >= 2 else float(proba_ens[0, 0])
        direction = "up" if up_prob >= self.threshold else "down"

        # 예측 대상 날짜: based_on_date의 다음 거래일 (단순히 +1일로 표시)
        import pandas as pd
        prediction_date = str(
            (pd.Timestamp(based_on_date) + pd.offsets.BDay(1)).date()
        )

        logger.info(
            f"[{self.ticker}] 예측 완료 → {direction} "
            f"(up_prob={up_prob:.3f}, A={proba_a:.3f}, B={proba_b:.3f}, C={proba_c:.3f})"
        )

        return {
            "ticker":           self.ticker,
            "prediction_date":  prediction_date,
            "based_on_date":    str(pd.Timestamp(based_on_date).date()),
            "direction":        direction,
            "up_probability":   round(up_prob, 4),
            "threshold_used":   self.threshold,
            "model_probabilities": {
                "model_a": round(proba_a, 4),
                "model_b": round(proba_b, 4),
                "model_c": round(proba_c, 4),
            },
        }
