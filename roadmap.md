# Stockmind-mini 업그레이드 로드맵

> 이 문서는 프로젝트의 진행 현황, 설계 결정 이유, 트러블슈팅 기록을 담은 개발 일지입니다.
> 나중에 돌아봤을 때 "왜 이런 결정을 했는지" 빠르게 파악할 수 있도록 작성했습니다.

---

## 개발 히스토리

### v1.0 - 기반 구축 (2026.02)

**한 일**
- Yahoo Finance API 직접 호출로 주가 수집
- Selenium으로 Yahoo Finance 뉴스 크롤링
- VADER 감정분석
- PostgreSQL DB 저장 (stock_prices, news_articles)
- FastAPI REST API 서버
- Docker 컨테이너화 + docker-compose
- GitHub Actions CI/CD
- AWS EC2 + ECR 배포

**설계 결정**
- yfinance 라이브러리 대신 requests로 직접 호출한 이유: Docker 환경에서 yfinance 내부 파싱 이슈가 발생했기 때문
- VADER 선택 이유: 별도 API 키 없이 빠르게 감정분석 구현 가능, 초기 프로토타입에 적합

**트러블슈팅**
- EC2 아웃바운드 보안그룹이 막혀있어서 패키지 설치 타임아웃 발생 → All traffic 허용으로 해결
- SSH 인바운드 규칙 미설정으로 접속 불가 → Anywhere 허용으로 해결
- Actions runner에서 Chrome 바이너리 경로가 달라서 크롤링 실패 → CHROME_BIN 환경변수로 경로 지정

---

### v1.1 - 아키텍처 변경 (2026.03)

**변경 내용**
- EC2 내부 Selenium 크롤링 → GitHub Actions runner로 이전

**변경 이유**
- t2.micro (RAM 1GB)에서 Chrome 실행 시 OOM(Out of Memory) 발생
- Actions runner는 RAM 7GB에 무료로 사용 가능
- EC2는 DB + API 서버만 담당하도록 역할 분리 → 안정성 향상

**배운 점**
- 서버 스펙에 맞게 역할을 분산하는 것이 중요
- CI/CD에서 크롤링을 실행하면 인프라 비용 없이 자원을 활용할 수 있음
- cd.yml을 deploy job과 pipeline job으로 분리하여 독립적으로 실행

---

### v1.2 - 데이터 확장 + 감정분석 고도화 (2026.03)

**추가한 것**
- 기술적 지표: MA5, MA20, MA60, RSI (기존 주가 데이터로 계산)
- 시장 지표: KOSPI(^KS11), KOSDAQ(^KQ11), 나스닥(^IXIC), VIX(^VIX)
- DB 테이블: market_indicators 추가
- 감정분석: VADER → GPT-4o-mini 교체
- sentiment_reason 컬럼 추가 (GPT 분석 이유 저장)

**제거한 것**
- 펀더멘털 수집 (시가총액, PER, PBR): Yahoo Finance quoteSummary API가 401 Unauthorized 반환
  → 추후 yfinance 라이브러리로 대체 예정

**설계 결정**
- VADER 대신 GPT-4o-mini를 선택한 이유:
  VADER는 일반 텍스트 기반으로 금융 도메인 특화도가 낮고,
  지정학적 리스크나 시사 이벤트 같은 간접적 맥락을 이해하지 못함.
  GPT-4o-mini는 이런 맥락까지 고려한 분석이 가능하고, 비용도 월 $1 미만으로 저렴.
- FinBERT 대신 GPT-4o-mini를 선택한 이유:
  FinBERT는 기업 실적 보고서에 특화되어 있어 시사/지정학 이벤트 맥락 이해가 약함.

**트러블슈팅**
- CI PostgreSQL service container는 매번 새로 생성되는 빈 DB라서 ALTER TABLE이 적용 안 됨
  → init_db()에 마이그레이션 로직(ALTER TABLE IF NOT EXISTS) 추가로 해결
- Docker 헬스체크 실패: 컨테이너에 curl이 없어서 127 ExitCode 반환
  → Dockerfile에 curl 설치 추가, 동시에 불필요한 Chrome/ChromeDriver 제거

---

### v1.3 - 과거 데이터 수집 (2026.03)

**한 일**
- backfill.py 작성 (1회성 과거 데이터 수집 스크립트)
- _period_to_days()에 "1y" 처리 추가
- 1년치 과거 데이터 수집 완료
  - 005930.KS: 243일치 (MA60: 184건, RSI: 229건)
  - TSLA: 251일치 (MA60: 192건, RSI: 237건)
  - 시장 지표: 991건

**설계 결정**
- 매일 cron(5d)과 별개로 1회성 스크립트로 과거 데이터 수집
  → settings.py의 PRICE_PERIOD를 건드리지 않아도 됨
  → 멱등성 보장 (upsert로 중복 데이터 자동 처리)

---

### v1.4 - 버그 픽스 (2026.03~04)

**수정한 것**
- 시장 지표 중복 upsert 버그: `upsert_market_indicators()`에 중복 데이터 사전 제거 로직 추가
- 주가 중복 upsert 버그: `upsert_stock_prices()`에 동일하게 중복 제거 적용
- Dockerfile 내용 중복: 동일한 멀티스테이지 빌드 블록이 두 번 작성된 문제 제거

**트러블슈팅**
- 같은 (ticker, date) 조합의 데이터가 배치 내에 두 번 이상 포함될 경우 ON CONFLICT가 동작하기 전에 PostgreSQL 유니크 제약 위반 발생 → upsert 호출 전 pandas로 중복 제거

---

## 현재 상태

```
✅ 주가 수집 (Yahoo Finance API)
✅ 기술적 지표 (MA5, MA20, MA60, RSI)
✅ 시장 지표 (KOSPI, KOSDAQ, 나스닥, VIX)
✅ 뉴스 수집 (Selenium)
✅ 감정분석 (GPT-4o-mini) + 분석 이유 저장
✅ DB 저장 (PostgreSQL 3개 테이블)
✅ 과거 1년치 데이터 확보 (backfill 완료)
✅ FastAPI REST API 서버
✅ Docker 컨테이너화
✅ CI/CD (GitHub Actions)
✅ AWS EC2 배포
✅ 매일 KST 09:00 자동 수집 (cron)
✅ feature → dev → main Git Flow
⏸️ 펀더멘털 수집 (Yahoo Finance 401로 보류)
```

---

## 2단계: 예측모델 설계

### 모델 설계 결정 (2026.03)

**왜 LSTM + XGBoost 스태킹인가?**
```
주가 데이터는 테이블 형태로 저장되어 있지만 본질은 시계열 데이터.
날짜의 흐름(어제 → 오늘 → 내일)이 예측에 중요.

LSTM 단독:
- 시계열 흐름 학습에 강함
- 테이블 feature(MA, RSI 등) 활용도는 상대적으로 낮음

XGBoost 단독:
- 테이블 feature 학습에 강함
- 시계열 순서 개념이 없음 (각 행을 독립적으로 봄)

→ LSTM + XGBoost 스태킹:
  LSTM이 시계열 패턴을 학습한 결과를
  XGBoost가 테이블 feature와 결합해서 최종 예측
  → 두 모델의 장점을 결합
```

**왜 CNNTransformer를 선택하지 않았나?**
```
ECG 데이터: 심장 박동이라는 명확한 반복 패턴 존재 → CNN 효과적
주가 데이터: 명확한 반복 패턴 없음 (비정형)
           → CNN의 국지적 패턴 감지 효과가 낮음
           → 데이터 250일치로 CNNTransformer 학습엔 부족
           → 추후 데이터 충분히 쌓이면 시도 가능
```

### Model A: LSTM + XGBoost 스태킹 (주가 데이터 기반)

```
✅ Feature 설계
   - 입력: 최근 20일치 시퀀스 (윈도우)
   - close, volume, price_change_pct
   - MA5, MA20, MA60, RSI
   - 시장 지표 (KOSPI/NASDAQ, VIX)

✅ LSTM 모델 학습
   - 출력: up/down/flat 확률값
   - 예측값을 XGBoost의 feature로 사용

✅ XGBoost 모델 학습
   - 입력: LSTM 출력 + 테이블 feature
   - 출력: 최종 up/down/flat
   - 학습된 모델: models/{ticker}_lstm_*.pt, models/{ticker}_xgb_*.pkl

⬜ 예측값을 feature A로 DB 저장
⬜ API 엔드포인트 추가 (/stocks/{ticker}/prediction)
```

### Model B: 차트패턴 기반 예측 (규칙 기반 + XGBoost)

```
설계 방향:
- 차트패턴을 이미지로 변환 후 CNN 분류는
  데이터가 더 쌓이면 시도 (현재는 데이터 부족)
- 규칙 기반 차트패턴 feature + XGBoost로 우선 구현

✅ 규칙 기반 차트패턴 feature 설계 (chart_features.py)
   - 골든크로스 (MA5 > MA20 교차) → 0/1
   - 데드크로스 (MA5 < MA20 교차) → 0/1
   - RSI 과매수 (RSI > 70) → 0/1
   - RSI 과매도 (RSI < 30) → 0/1

✅ XGBoost 모델 학습 (train_b.py)
⬜ 예측값을 feature B로 DB 저장
```

---

## 3단계: 감정분석 기반 예측모델 (Model C)

```
(뉴스 감정분석 데이터가 충분히 쌓인 후 진행)

⬜ 감정분석 feature 설계
   - 일별 감정점수 평균
   - 긍정/부정 기사 비율
   - 감정 추세 (3일/7일 이동평균)

⬜ 모델 학습 → 예측값을 feature C로 저장
```

---

## 4단계: 앙상블 메타모델 (최종 예측)

```
설계 방향:
- 스태킹 방식: 각 모델의 예측값을 새로운 feature로 사용
- 백테스팅으로 각 모델 정확도 측정 → 가중치 자동 튜닝
- 최종 출력: 종가 예측 (회귀)

금융 데이터 특성상 단일 모델 신뢰도 낮음 (60~65%면 의미있음)
→ 여러 모델 신호를 종합하는 앙상블이 더 신뢰도 높음
→ "맞다/틀리다"가 아닌 "확률적으로 더 나은 판단을 돕는 도구"로 설계

⬜ feature A (Model A 예측) +
   feature B (Model B 예측) +
   feature C (감정분석 예측) 결합
⬜ 가중치 설계 및 백테스팅으로 최적화
⬜ 최종 종가 예측 (회귀)
⬜ 백테스팅
```

---

## 5단계: AI Agent

```
⬜ LangGraph Agent 구성
⬜ 도구: DB조회, 실시간 뉴스 검색, 예측결과 조회
⬜ 자연어 질문 대응
   예: "삼성전자 지금 사도 돼?"
```

---

## 단계별 진행 현황

| 단계 | 상태 | 시작일 | 완료일 |
|------|------|--------|--------|
| v1.0 기반 구축 | ✅ 완료 | 2026.02 | 2026.02 |
| v1.1 아키텍처 변경 | ✅ 완료 | 2026.03 | 2026.03 |
| v1.2 데이터 확장 | ✅ 완료 | 2026.03 | 2026.03 |
| v1.3 과거 데이터 수집 | ✅ 완료 | 2026.03 | 2026.03 |
| v1.4 버그 픽스 | ✅ 완료 | 2026.03 | 2026.04 |
| 2단계 Model A (LSTM+XGBoost) | 🔄 학습완료, 통합 대기 | 2026.03 | - |
| 2단계 Model B (차트패턴) | 🔄 학습완료, 통합 대기 | 2026.04 | - |
| 3단계 Model C (감정분석) | ⬜ 대기 | - | - |
| 4단계 앙상블 메타모델 | ⬜ 대기 | - | - |
| 5단계 AI Agent | ⬜ 대기 | - | - |
