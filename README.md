# 📈 Stockmind Mini

삼성전자(005930.KS)와 테슬라(TSLA)의 주가 데이터 및 뉴스 감정분석을 매일 자동 수집하고 API로 제공하는 경량 데이터 파이프라인.

> 단순한 데이터 수집을 넘어, 주가 예측 모델과 AI Agent로 발전시키는 것을 목표로 진행 중인 프로젝트입니다.

---

## 프로젝트 목적

- 삼성전자 · 테슬라 주가 흐름 파악 및 투자 인사이트 확보
- 뉴스 감정분석을 통한 주가 흐름 사전 파악
- 기술적 지표 · 시장 지표 · 감정분석을 결합한 앙상블 예측 모델 구축 (진행 중)
- CI/CD 자동화 파이프라인 구축 실습

---

## 현재 아키텍처

```
GitHub Actions (매일 KST 09:00 cron)
    ↓
Actions Runner (RAM 7GB, 무료)
├── 주가 수집         (Yahoo Finance API 직접 호출)
├── 기술적 지표 계산  (MA5, MA20, MA60, RSI)
├── 시장 지표 수집    (KOSPI, KOSDAQ, 나스닥, VIX)
├── 뉴스 링크 수집    (Selenium + Chromium)
├── 기사 본문 수집    (HTTP + Selenium fallback)
├── 감정 분석         (GPT-4o-mini)
└── EC2 DB 직접 저장  (PostgreSQL)

EC2 (24시간 상주)
├── PostgreSQL  (데이터 저장)
└── FastAPI     (API 서버)
```

### 아키텍처 결정 이유

초기 설계에서는 EC2 내부에서 Selenium 크롤링을 실행했으나, t2.micro (RAM 1GB) 환경에서 Chrome이 메모리 부족으로 타임아웃이 발생했다. 이를 해결하기 위해 크롤링과 감정분석을 **GitHub Actions runner (RAM 7GB, 무료)** 에서 실행하고, 결과만 EC2 DB에 저장하는 구조로 변경했다. EC2는 DB와 API 서버만 담당하여 안정적으로 운영된다.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Language | Python 3.10 |
| Web Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL 16 |
| Crawling | Selenium, Requests |
| NLP | GPT-4o-mini (OpenAI API) |
| Container | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Cloud | AWS EC2, ECR |

---

## 프로젝트 구조

```
stockmind-mini/
├── src/
│   ├── collector/
│   │   ├── price_fetcher.py    # 주가 + 기술적 지표 + 시장 지표 수집
│   │   ├── yahoo_scraper.py    # 뉴스 링크 수집 (Selenium + CHROME_BIN 지원)
│   │   ├── article_fetcher.py  # 기사 본문 수집
│   │   └── http_utils.py       # HTTP 유틸리티
│   ├── analyzer/
│   │   └── sentiment.py        # GPT-4o-mini 감정 분석
│   ├── db/
│   │   ├── models.py           # DB 테이블 정의
│   │   └── writer.py           # DB 저장 (upsert, 중복방지)
│   ├── api/
│   │   └── main.py             # FastAPI 엔드포인트
│   ├── ml/
│   │   ├── features.py         # Model A feature 엔지니어링 (LSTM 시퀀스)
│   │   ├── chart_features.py   # Model B feature 엔지니어링 (차트패턴)
│   │   ├── lstm_model.py       # LSTM 모델 정의
│   │   ├── xgb_model.py        # XGBoost 모델 정의
│   │   ├── train_a.py          # Model A 학습 (LSTM+XGBoost 스태킹)
│   │   └── train_b.py          # Model B 학습 (차트패턴 + XGBoost)
│   ├── main.py                 # 파이프라인 오케스트레이터
│   └── settings.py             # 환경변수 설정
├── tests/
│   ├── test_collector.py       # 수집 모듈 테스트
│   ├── test_analyzer.py        # 감정분석 테스트 (mock)
│   └── test_db.py              # DB 테스트 (mock)
├── .github/
│   └── workflows/
│       ├── ci.yml              # PR 시 자동 테스트
│       └── cd.yml              # main 머지 시 자동 배포 + 매일 cron 수집
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## 설치 및 실행

### 사전 요구사항
- Docker Desktop
- Python 3.10+

### 로컬 실행

```bash
# 레포 클론
git clone https://github.com/Shin-junyeob/stockmind-mini.git
cd stockmind-mini

# 환경변수 설정
cp .env.example .env

# 컨테이너 실행
docker compose up -d db api

# 파이프라인 수동 실행
PYTHONPATH=src python src/main.py
```

### 환경변수 (.env)

```
DATABASE_URL=postgresql://stockmind:stockmind@db:5432/stockmind
OPENAI_API_KEY=sk-...
YF_MAX_SCROLL=10
YF_MAX_ARTICLES=30
PRICE_PERIOD=5d
PRICE_INTERVAL=1d
```

---

## DB 테이블 구조

| 테이블 | 설명 |
|--------|------|
| stock_prices | 일별 주가 + MA5/MA20/MA60/RSI |
| news_articles | 뉴스 기사 + GPT 감정분석 결과 |
| market_indicators | KOSPI, KOSDAQ, 나스닥, VIX |
| fundamentals | 시가총액, PER, PBR (수집 보류) |

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 서버 상태 확인 |
| GET | `/stocks/{ticker}/prices` | 주가 이력 조회 |
| GET | `/stocks/{ticker}/news` | 뉴스 감정분석 이력 조회 |
| GET | `/stocks/{ticker}/summary` | 날짜별 주가 + 감정 요약 |

Swagger UI: `http://[EC2_HOST]:8000/docs`

---

## CI/CD 파이프라인

### CI (ci.yml)
- **트리거**: PR 생성 시 (dev, main 대상)
- **동작**: pytest 자동 실행
- **효과**: 테스트 실패 시 머지 불가

### CD (cd.yml)
두 개의 독립적인 job으로 구성.

**deploy job** (main 머지 시에만 실행)
1. Docker 이미지 빌드 → AWS ECR 푸시
2. EC2에 SSH 접속 → 최신 이미지 배포

**pipeline job** (main 머지 시 + 매일 KST 09:00 cron)
1. Actions runner에서 주가 · 뉴스 수집
2. GPT-4o-mini 감정분석
3. EC2 PostgreSQL DB에 직접 저장

### Git Flow
```
feature/* → dev → main
    ↓          ↓      ↓
  개발       CI    CI + CD
```

---

## 트러블슈팅 기록

| 문제 | 원인 | 해결 |
|------|------|------|
| EC2 Selenium 타임아웃 | t2.micro RAM 부족 (1GB) | Actions runner로 크롤링 이전 |
| yfinance Docker 오류 | yfinance 내부 파싱 이슈 | requests로 Yahoo Finance API 직접 호출 |
| EC2 패키지 설치 타임아웃 | 아웃바운드 보안그룹 미설정 | 아웃바운드 All traffic 허용 |
| Chrome 바이너리 없음 | Actions runner Chrome 경로 상이 | CHROME_BIN 환경변수로 경로 지정 |
| CI DB 컬럼 없음 | init_db가 ALTER TABLE 미실행 | init_db에 마이그레이션 로직 추가 |
| 펀더멘털 수집 401 에러 | Yahoo Finance API 정책 변경 | 펀더멘털 수집 보류, 추후 yfinance로 대체 예정 |
| Docker healthcheck 실패 | 컨테이너에 curl 미설치 | Dockerfile에 curl 추가 |
| 시장 지표/주가 upsert 오류 | 배치 내 중복 데이터로 PostgreSQL 유니크 제약 위반 | upsert 전 pandas 중복 제거 로직 추가 |
| Dockerfile 빌드 오류 | 멀티스테이지 블록 중복 작성 | 중복 블록 제거 |

---

## 향후 개발 계획

- [x] 과거 데이터 수집 (backfill.py)
- [x] Model A: 주가 기반 예측 모델 (LSTM + XGBoost 스태킹) - 학습 완료
- [x] Model B: 차트패턴 기반 예측 모델 (규칙 기반 feature + XGBoost) - 학습 완료
- [ ] Model A/B 예측값 DB 저장 + API 엔드포인트 추가
- [ ] Model C: 감정분석 기반 예측 모델
- [ ] 앙상블 메타모델 (Model A + B + C, 가중치 튜닝)
- [ ] 백테스팅 (예측 정확도 검증)
- [ ] AI Agent (LangGraph, 자연어 투자 인사이트)
