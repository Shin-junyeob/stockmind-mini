"""
lstm_model.py - LSTM 모델

시계열 시퀀스를 입력받아 up/down/flat 방향을 예측.
출력값(확률)은 XGBoost의 feature로 사용됨.
"""

import logging
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.utils.class_weight import compute_class_weight

logger = logging.getLogger(__name__)


class LSTMClassifier(nn.Module):
    """
    LSTM 기반 방향 분류 모델.

    구조:
    LSTM (2층) → Dropout → Fully Connected → Softmax
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        num_classes: int = 3,   # up / flat / down
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, window, features)
        out, _ = self.lstm(x)
        out = out[:, -1, :]       # 마지막 타임스텝
        out = self.dropout(out)
        out = self.fc(out)
        return out                # (batch, num_classes) - logits


def train_lstm(
    X_seq: np.ndarray,
    y: np.ndarray,
    input_size: int,
    epochs: int = 50,
    batch_size: int = 32,
    lr: float = 1e-3,
    val_ratio: float = 0.2,
) -> LSTMClassifier:
    """
    LSTM 모델 학습.

    Args:
        X_seq: (samples, window, features)
        y:     (samples,) - 0/1/2
        input_size: feature 수
    Returns:
        학습된 LSTMClassifier
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"[lstm] 학습 시작 | device={device} | samples={len(X_seq)}")

    # Train / Val 분할 (시계열이라 shuffle 없이 앞뒤로 분할)
    split = int(len(X_seq) * (1 - val_ratio))
    X_train, X_val = X_seq[:split], X_seq[split:]
    y_train, y_val = y[:split],     y[split:]

    # Tensor 변환
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    X_val_t   = torch.tensor(X_val,   dtype=torch.float32)
    y_val_t   = torch.tensor(y_val,   dtype=torch.long)

    train_loader = DataLoader(
        TensorDataset(X_train_t, y_train_t),
        batch_size=batch_size,
        shuffle=False,   # 시계열 순서 유지
    )

    # 모델 / 옵티마이저 / 손실함수
    n_classes = len(np.unique(y_train))
    model = LSTMClassifier(input_size=input_size, num_classes=n_classes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    
    classes = np.unique(y_train)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_train)
    weight_tensor = torch.tensor(weights, dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=weight_tensor)

    best_val_loss = float("inf")
    best_state = None

    for epoch in range(1, epochs + 1):
        # ── 학습 ──────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            logits = model(X_batch)
            loss = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        train_loss /= len(train_loader)

        # ── 검증 ──────────────────────────────────────────────
        model.eval()
        with torch.no_grad():
            val_logits = model(X_val_t.to(device))
            val_loss   = criterion(val_logits, y_val_t.to(device)).item()
            val_preds  = val_logits.argmax(dim=1).cpu().numpy()
            val_acc    = (val_preds == y_val).mean()

        # Best 모델 저장
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 10 == 0:
            logger.info(
                f"[lstm] epoch {epoch:3d}/{epochs} | "
                f"train_loss={train_loss:.4f} | "
                f"val_loss={val_loss:.4f} | "
                f"val_acc={val_acc:.4f}"
            )

    # Best 모델 복원
    model.load_state_dict(best_state)
    logger.info(f"[lstm] 학습 완료 | best_val_loss={best_val_loss:.4f}")
    return model


def predict_proba_lstm(
    model: LSTMClassifier,
    X_seq: np.ndarray,
) -> np.ndarray:
    """
    LSTM 예측 확률값 반환.
    XGBoost의 feature로 사용됨.

    Returns:
        proba: (samples, 3) - [down 확률, flat 확률, up 확률]
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    X_t = torch.tensor(X_seq, dtype=torch.float32).to(device)

    with torch.no_grad():
        logits = model(X_t)
        proba  = torch.softmax(logits, dim=1).cpu().numpy()

    return proba   # (samples, 3)
