Scan the entire ML codebase for data leakage patterns. Read each file carefully and report findings with file path, line number, severity, and fix.

## Files to scan

Read ALL of the following files:
- `src/ml/features.py`
- `src/ml/chart_features.py`
- `src/ml/sentiment_features.py`
- `src/ml/lstm_model.py`
- `src/ml/xgb_model.py`
- `src/ml/train_a.py`
- `src/ml/train_b.py`
- `src/ml/train_c.py`
- `src/ml/train_ensemble.py`
- `src/ml/predictor.py`
- `src/collector/price_fetcher.py`

---

## Leakage Patterns to Check

### L1. Lookahead Bias (미래 데이터 사용)
- `shift(-N)` 을 feature 컬럼에 적용하는 경우 (label에는 정상, feature에는 금지)
- rolling/ewm 계산 시 `min_periods` 가 없어서 NaN이 채워지는 방식 확인
- `ffill()` 이 test 구간의 NaN을 train 구간 값으로 채우지 않는지 확인

### L2. Scaler Leakage (전체 데이터로 fit)
- `StandardScaler().fit()` 또는 `fit_transform()` 이 train split 이전 전체 데이터에 적용되는지 확인
- 올바른 패턴: `scaler.fit(X_train)` → `scaler.transform(X_val)`, `scaler.transform(X_test)`
- 잘못된 패턴: `scaler.fit(X_all)` or `scaler.fit_transform(X_all)`

### L3. Target Leakage (label과 동일 정보 포함)
- `direction` 컬럼이 feature로 사용되는 경우
- `price_change` 또는 `price_change_pct` 가 당일 label 예측에 쓰이는 경우 (이건 OK — 다음날 label을 예측하는 것이므로)
- `close` 가 당일 종가인데 당일 direction label 생성에 쓰이는 경우

### L4. Ensemble/Stacking Leakage
- `train_ensemble.py` 에서 base 모델들이 전체 데이터에 대한 in-sample 예측을 반환하는지 확인
- `get_proba_a/b/c()` 함수가 훈련 구간에 대한 예측을 포함하는지 확인
- Meta XGBoost 학습 구간이 base 모델 훈련 구간과 겹치는지 확인

### L5. Train/Test Split 순서
- 시계열 데이터에서 `shuffle=True` 또는 random split 사용 여부
- test 데이터가 train 데이터보다 시간적으로 이전인 경우
- purge gap (window_size 만큼의 간격) 부재 — LSTM 20일 윈도우 사용 시 train 마지막 행과 test 첫 행 사이에 20일 이상 간격이 없으면 시퀀스가 겹침

### L6. Feature Engineering Leakage
- `price_change = close - open` (당일 open/close 모두 사용 → 이 자체는 leakage 아님. 단, direction label과의 관계 확인)
- `direction` label이 `close - open > 0` 기준인지 `close / prev_close - 1 > 0` 기준인지 확인 (후자가 올바름)
- 뉴스 감성 feature가 당일 date 기준으로 join되는지, 다음 거래일 기준으로 join되는지 확인

---

## Output Format

```
# Data Leakage 스캔 보고서

## 요약
- 스캔한 파일 수: N
- 발견된 이슈: Critical N개 / Warning N개 / Info N개

---

## Critical (즉시 수정 필요)

### [파일명:라인번호] 이슈 제목
- **유형**: L1~L6 중 해당
- **코드**: `문제가 되는 코드 스니펫`
- **문제**: 왜 leakage인지
- **수정**: 올바른 코드 또는 접근법

---

## Warning (수정 권장)
(동일 형식)

---

## Info (확인 필요)
(동일 형식)

---

## 통과 항목
- [파일명] 검토 완료 — 이슈 없음
```

스캔 완료 후, Critical 이슈가 있다면 수정 여부를 물어볼 것.
