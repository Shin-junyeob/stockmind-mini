"""
xgb_model.py - XGBoost 모델

LSTM 출력 확률값 + 테이블 feature를 결합하여
최종 up/down/flat 방향을 예측.
"""

import logging
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight

logger = logging.getLogger(__name__)


def build_xgb_features(
    lstm_proba: np.ndarray,
    X_tab: np.ndarray,
) -> np.ndarray:
    """
    LSTM 확률값 + 테이블 feature 결합.

    Args:
        lstm_proba: (samples, 3) - LSTM 출력 확률 [down, flat, up]
        X_tab:      (samples, features) - 당일 테이블 feature

    Returns:
        X_combined: (samples, 3 + features)
    """
    X_combined = np.hstack([lstm_proba, X_tab])
    logger.info(f"[xgb] feature 결합 완료: shape={X_combined.shape}")
    return X_combined


def train_xgb(
    X: np.ndarray,
    y: np.ndarray,
    val_ratio: float = 0.2,
) -> xgb.XGBClassifier:
    """
    XGBoost 모델 학습.
    y는 0부터 연속적인 정수여야 함 (호출 전에 재매핑 필요).

    Args:
        X: (samples, features) - LSTM 확률 + 테이블 feature 결합
        y: (samples,) - 0부터 연속적인 정수 (재매핑 완료된 값)

    Returns:
        학습된 XGBClassifier
    """
    n_classes = len(np.unique(y))

    # Train / Val 분할 (시계열 순서 유지)
    split = int(len(X) * (1 - val_ratio))
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    logger.info(f"[xgb] 학습 시작 | train={len(X_train)} val={len(X_val)} classes={n_classes}")

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42,
        early_stopping_rounds=20,
        nthread=1,
        num_class=n_classes,
        objective="multi:softprob",
    )

    sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)

    model.fit(
        X_train, y_train,
        sample_weight=sample_weights,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # 예측값 변환 (multi:softprob → argmax)
    raw_preds = model.predict(X_val)
    val_preds = np.argmax(raw_preds, axis=1) if raw_preds.ndim == 2 else raw_preds

    val_acc = accuracy_score(y_val, val_preds)
    logger.info(f"[xgb] 학습 완료 | val_acc={val_acc:.4f}")
    logger.info(
        f"[xgb] 분류 리포트:\n"
        f"{classification_report(y_val, val_preds, zero_division=0)}"
    )

    # Feature 중요도 상위 5개
    importance = model.feature_importances_
    top5_idx = np.argsort(importance)[::-1][:5]
    logger.info(f"[xgb] feature 중요도 상위 5개: {top5_idx} → {importance[top5_idx]}")

    return model


def predict_xgb(
    model: xgb.XGBClassifier,
    X: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    XGBoost 최종 예측.

    Returns:
        preds:  (samples,) - 예측 클래스 (재매핑된 값)
        proba:  (samples, n_classes) - 예측 확률
    """
    raw_preds = model.predict(X)
    if raw_preds.ndim == 2:
        preds = np.argmax(raw_preds, axis=1)
        proba = raw_preds
    else:
        preds = raw_preds
        proba = model.predict_proba(X)
    return preds, proba
