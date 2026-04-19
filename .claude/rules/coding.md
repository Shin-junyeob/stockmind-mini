# Coding Rules

## Python 컨벤션

- Python 3.10, 타입 힌트 사용 (`list[str]` not `List[str]`)
- 환경변수는 모두 `src/settings.py`에서 관리
- `create_engine(DATABASE_URL)`은 `src/db/writer.py`에서만 호출. 다른 파일은 `from db.writer import engine` 사용

## DB 모델 변경 시

`src/db/models.py` 수정 → `src/db/writer.py`의 `init_db()`에 마이그레이션 추가

```python
# init_db() 안에 추가하는 패턴
"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {type}"
```

CI PostgreSQL은 빈 DB로 시작하므로 `IF NOT EXISTS` 패턴 필수.

## 데이터 누수 방지

- `price_change`: `close / prev_close - 1` (`close - open` 금지)
- `direction` label: 전일 종가 대비 당일 종가 기준
- Scaler: 학습 데이터(60%) 구간으로만 `fit`, 나머지는 `transform`
- LSTM 예측: out-of-fold만 XGBoost 학습에 사용
- 앙상블 Meta XGBoost: base 모델 훈련 구간(60%) 제외한 뒤 40%로만 학습
- 시계열 split: 항상 날짜 순서 유지 (shuffle 금지)

## 모델 파일 네이밍

```
models/{ticker}_{type}_{YYYYMMDD}.ext
```

| 패턴 | 모델 |
|------|------|
| `_lstm_`, `_xgb_`, `_scaler_`, `_meta_` | Model A |
| `_b_xgb_` | Model B |
| `_c_xgb_`, `_c_meta_` | Model C |
| `_ensemble_xgb_` | Ensemble |
| `_threshold.json` | 임계값 |

`predictor.py`는 glob으로 최신 파일 자동 선택 (`sorted()[-1]`).

## ML 파일 위치

새 ML 파일은 `src/ml/` 하위에 위치.

## 테스트

- `tests/` 하위, pytest 사용
- DB 의존 테스트는 mock 사용
- OpenAI API 호출 테스트는 mock 필수
- 새 기능 추가 시 테스트 파일도 함께 작성
