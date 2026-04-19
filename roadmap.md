# Stockmind Mini — 개발 로드맵

> 작업 전 이 파일을 먼저 읽고 현재 상태와 다음 할 일을 파악한다.
> 대화 중 추가/변경 사항이 생기면 이 파일을 업데이트한다.

---

## 다음 할 일

### Phase 2 — 자동화

| 항목 | 설명 | 상태 |
|------|------|------|
| Phase 2-1 | ML 재학습 자동화 — `cd.yml` retrain job + `src/ml/eval_compare.py` (up_f1 +2% 이상일 때만 교체) | ✅ |
| Phase 2-2 | 모델 성능 모니터링 API — `GET /models/status` (prediction_logs 최근 30일 accuracy 집계) | ⬜ |
| Phase 2-3 | 예측 알림 — `src/notify.py` Gmail 전송 (매일 predict 완료 후, 자격증명 없으면 스킵) | ✅ |

### Phase 3 — AI Agent

| 항목 | 설명 | 상태 |
|------|------|------|
| Phase 3 | LangGraph ReAct Agent — `GET /agent/ask?ticker=...&q=...`, Claude API(haiku) 활용, 자연어 투자 인사이트 | ⬜ |

### Phase 4 — 장기 확장 (보류)

| 아이디어 | 조건 | 기대 효과 |
|---------|------|----------|
| Cross-sectional learning | ticker 300개 확장 | 샘플 2,400 → 9,000+ |
| 펀더멘털 수집 재개 | yfinance 대체 소스 확보 | PER/PBR feature |
| Transformer 모델 | 데이터 안정화 후 | LSTM 대체 |

---

## 완료된 항목

```
✅ 데이터 수집 파이프라인 (주가, 기술적 지표, 시장 지표, 뉴스, 감정분석)
✅ 매일 KST 09:00 GitHub Actions 자동 수집
✅ Model A — LSTM + XGBoost 스태킹 (20일 window, binary classification)
✅ Model B — 차트패턴 33 features + XGBoost
✅ Model C — Fear & Greed + VIX + 뉴스 감성 XGBoost (3 stage 비교 후 best 선택)
✅ Ensemble — Meta XGBoost (Model A/B/C up 확률 결합)
✅ ML 전체 학습 오케스트레이터 (train.py: A→B→C→Ensemble)
✅ 예측 API (GET /stocks/{ticker}/prediction, threshold 자동 로드)
✅ CI/CD (GitHub Actions), Docker, AWS EC2 배포
✅ 하네스 엔지니어링 (Rules, Skills, Hooks, MCP)

✅ P0 버그 수정 (2026-04-19)
  - price_change = close / prev_close - 1 기준 수정
    ⚠️ 2026-04-19 이전 수집 데이터의 direction 값은 잘못된 기준으로 저장됨.
       재학습 전 backfill 재실행 필요.
  - volume 컬럼 BigInteger 변경
  - 앙상블 leakage 수정 (overlap_cutoff = int(len(df) * 0.6))

✅ Phase 1 — 예측 신뢰성 확보 (2026-04-19)
  - Phase 1-1: prediction_logs 테이블, 예측 DB 로깅, actual_direction 사후 업데이트
  - Phase 1-2: backtest.py, GET /stocks/{ticker}/backtest
  - Phase 1-3: tune_threshold.py, models/{ticker}_threshold.json → predictor 자동 적용
```

---

## 개발 히스토리

### v1.0 — 기반 구축 (2026.02)

- Yahoo Finance API 직접 호출로 주가 수집
- Selenium 뉴스 크롤링, VADER 감정분석
- PostgreSQL + FastAPI + Docker + GitHub Actions CI/CD + AWS EC2 배포

**결정**: yfinance 대신 requests 직접 호출 — Docker 환경에서 yfinance 내부 파싱 이슈 발생

**트러블슈팅**
- EC2 아웃바운드 보안그룹 막힘 → All traffic 허용
- Actions runner Chrome 경로 상이 → `CHROME_BIN` 환경변수로 지정

---

### v1.1 — 아키텍처 변경 (2026.03)

- EC2 내부 Selenium 크롤링 → GitHub Actions runner로 이전

**결정**: EC2 t2.micro(RAM 1GB)에서 Chrome OOM 발생. Actions runner(RAM 7GB, 무료)에서 크롤링·감정분석 실행, 결과만 EC2 DB 저장. EC2는 DB + API만 담당.

---

### v1.2 — 데이터 확장 + 감정분석 고도화 (2026.03)

- 기술적 지표 추가: MA5, MA20, MA60, RSI
- 시장 지표 추가: KOSPI, KOSDAQ, 나스닥, VIX
- 감정분석: VADER → GPT-4o-mini 교체, sentiment_reason 컬럼 추가
- 펀더멘털 수집 보류 (Yahoo Finance quoteSummary API 401 반환)

**결정**: FinBERT 대신 GPT-4o-mini 선택 — FinBERT는 기업 실적 보고서 특화, 시사/지정학 맥락 이해 약함. GPT-4o-mini는 맥락 이해 가능하고 비용 월 $1 미만.

**트러블슈팅**
- CI PostgreSQL은 매번 빈 DB → `init_db()`에 `ALTER TABLE IF NOT EXISTS` 마이그레이션 추가
- Docker healthcheck 실패 (curl 없음) → Dockerfile에 curl 추가

---

### v1.3 — 과거 데이터 수집 (2026.03~04)

- backfill.py 작성, 5년치 과거 데이터 수집 완료
  - 005930.KS: 1,221일 / TSLA: 1,254일 / 시장 지표: 4,951건
- stock_prices에 high/low 컬럼 추가

---

### v1.4 — 버그 픽스 (2026.03~04)

- 배치 내 중복 데이터로 upsert PostgreSQL 유니크 제약 위반 → upsert 전 pandas `.drop_duplicates()`
- Dockerfile 멀티스테이지 빌드 블록 중복 제거

---

### v1.5 — ML 모델 개선 (2026.04)

- Data Leakage 수정: Scaler를 학습 구간에서만 fit, LSTM out-of-fold 예측 사용
- 클래스 불균형 처리: LSTM에 class weight, XGBoost에 sample weight 적용
- 3-class → binary 분류: flat → down으로 통합 (`label_map = {"up": 1, "flat": 0, "down": 0}`)
- LSTM 구조 단순화: 2-layer hidden=64 → 1-layer hidden=32
- Model B feature 33개로 확장 (캔들스틱, Stochastic, ATR, OBV, ROC 추가)

---

### v1.6 — Model C (감성 기반 예측) (2026.04)

- sentiment_features.py: Stage 2(Fear&Greed) / Stage 3(+VIX) / Stage 4(+뉴스) 3가지 전략
- train_c.py: up_f1 기준 최고 stage 자동 선택 후 저장

**결정**: Finnhub 포기 — TSLA 1년치만 가능, 005930.KS 접근 불가. CNN Fear & Greed Index는 2021년~현재 5년치 완전 수집 가능, 주가 데이터와 기간 일치.

---

### v1.7 — 앙상블 + 예측 API (2026.04)

- train_ensemble.py: Model A/B/C up 확률 → Meta XGBoost
- train.py: A→B→C→Ensemble 단일 진입점
- predictor.py: EnsemblePredictor (서버 시작 시 1회 로드 후 캐싱)
- `GET /stocks/{ticker}/prediction` 엔드포인트

---

### v1.8 — Phase 1: 예측 신뢰성 확보 (2026.04.19)

**Phase 1-1: prediction_logs 테이블**
- `src/db/models.py`: PredictionLog ORM 추가
- `src/db/writer.py`: `insert_prediction_log()`, `update_prediction_actuals()` 추가
- `src/api/main.py`: `/prediction` 호출 시 DB 로깅 (실패해도 예측 결과 정상 반환)
- `src/main.py`: 주가 수집 후 전날 예측의 actual_direction / is_correct 자동 업데이트

**Phase 1-2: 백테스팅**
- `src/ml/backtest.py`: frozen 모델로 기간 시뮬레이션
- `GET /stocks/{ticker}/backtest?start=YYYY-MM-DD&end=YYYY-MM-DD&threshold=0.55`
- 응답: accuracy, traded_accuracy, n_traded, daily_results

**Phase 1-3: 임계값 튜닝**
- `src/ml/tune_threshold.py`: threshold 0.50~0.70 탐색, coverage ≥ 30% 조건
- `models/{ticker}_threshold.json` 저장
- `predictor.py`: 시작 시 threshold.json 자동 로드, `up_prob >= threshold` 기준 direction 판단

**결정**
- 로깅 실패가 API 가용성에 영향을 주면 안 됨 → try/except로 분리
- 백테스트는 fixed-model simulation (true walk-forward는 Phase 2-1 재학습 이후 가능)
- coverage 조건(≥ 30%)은 신호 빈도 보장을 위해 설정
