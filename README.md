# Stockmind Mini

삼성전자(005930.KS)와 테슬라(TSLA)의 주가를 매일 자동 수집하고, 앙상블 ML 모델로 다음 날 방향(상승/하락)을 예측하는 경량 파이프라인.

---

## 무엇을 하는 프로젝트인가

매일 아침 GitHub Actions가 자동으로 실행되어:

1. 주가 + 기술적 지표(MA, RSI)를 수집한다
2. 시장 지표(KOSPI, NASDAQ, VIX)를 수집한다
3. 뉴스를 크롤링하고 GPT-4o-mini로 감정을 분석한다
4. 수집된 데이터를 PostgreSQL DB에 저장한다

저장된 데이터를 기반으로 세 가지 모델이 독립적으로 예측하고, 앙상블 메타모델이 최종 방향을 결정한다.

```
Model A (LSTM + XGBoost)  ─┐
Model B (차트패턴 XGBoost)  ├──► Ensemble Meta XGBoost ──► up / down
Model C (감성 XGBoost)    ─┘
```

예측 결과는 REST API로 제공되며, 예측 정확도는 prediction_logs 테이블에 자동으로 기록된다.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Language | Python 3.10 |
| ML | PyTorch (LSTM), XGBoost, scikit-learn |
| Web Framework | FastAPI |
| Database | PostgreSQL 16 |
| Crawling | Selenium, Requests |
| NLP | GPT-4o-mini (OpenAI API) |
| Container | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Cloud | AWS EC2, ECR |

---

## 아키텍처

```
GitHub Actions (매일 KST 09:00)
    ├── 주가 / 시장 지표 수집
    ├── 뉴스 크롤링 + GPT 감정분석
    └── EC2 PostgreSQL에 저장

EC2 (24시간)
    ├── PostgreSQL  — 수집 데이터 + 예측 로그
    └── FastAPI     — 예측 API 서버
```

> EC2 t2.micro(RAM 1GB)에서 Selenium을 실행하면 OOM이 발생한다.
> 크롤링과 감정분석은 RAM 7GB인 Actions runner에서 실행하고, 결과만 EC2 DB에 저장하는 구조를 택했다.

---

## 로컬 실행

### 사전 요구사항

- Docker Desktop
- Python 3.10+

### 실행

```bash
git clone https://github.com/Shin-junyeob/stockmind-mini.git
cd stockmind-mini

# 환경변수 설정
cp .env.example .env  # DATABASE_URL, OPENAI_API_KEY 입력

# DB + API 서버 실행
docker compose up -d db api

# 데이터 수집 (수동 실행)
PYTHONPATH=src python src/main.py

# ML 학습 (Model A → B → C → Ensemble 순서)
PYTHONPATH=src python src/ml/train.py

# 임계값 튜닝 (학습 완료 후)
PYTHONPATH=src python src/ml/tune_threshold.py
```

### 환경변수 (.env)

```
DATABASE_URL=postgresql://stockmind:stockmind@db:5432/stockmind
OPENAI_API_KEY=sk-...
```

---

## API

Swagger UI: `http://[EC2_HOST]:8000/docs`

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 서버 상태 |
| GET | `/stocks/{ticker}/prices` | 주가 이력 |
| GET | `/stocks/{ticker}/news` | 뉴스 감정분석 이력 |
| GET | `/stocks/{ticker}/summary` | 날짜별 주가 + 감정 요약 |
| GET | `/stocks/{ticker}/prediction` | 앙상블 예측 (up/down + 확률) |
| GET | `/stocks/{ticker}/backtest` | 기간 백테스팅 (`?start=YYYY-MM-DD&end=YYYY-MM-DD&threshold=0.55`) |

---

## 테스트

```bash
pytest tests/ -v
```
