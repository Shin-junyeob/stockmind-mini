# 📈 Stockmind Mini

삼성전자(005930.KS)와 테슬라(TSLA)의 주가 데이터 및 뉴스 감정분석을 매일 자동 수집하고 API로 제공하는 경량 데이터 파이프라인.

---

## 프로젝트 목적

- 삼성전자 주가 흐름 파악 및 투자 인사이트 확보
- 일론 머스크 관련 뉴스 감정분석을 통한 테슬라 주가 흐름 사전 파악
- CI/CD 자동화 파이프라인 구축 실습

---

## 아키텍처

```
GitHub Actions (매일 KST 09:00 cron)
    ↓
Actions Runner (RAM 7GB, 무료)
├── 주가 수집       (Yahoo Finance API 직접 호출)
├── 뉴스 링크 수집  (Selenium + Chromium)
├── 기사 본문 수집  (HTTP + Selenium fallback)
├── 감정 분석       (VADER)
└── EC2 DB 직접 저장 (PostgreSQL)

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
| NLP | VADER Sentiment |
| Container | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Cloud | AWS EC2, ECR |

---

## 프로젝트 구조

```
stockmind-mini/
├── src/
│   ├── collector/
│   │   ├── price_fetcher.py    # 주가 수집 (Yahoo Finance API 직접 호출)
│   │   ├── yahoo_scraper.py    # 뉴스 링크 수집 (Selenium + CHROME_BIN 지원)
│   │   ├── article_fetcher.py  # 기사 본문 수집
│   │   └── http_utils.py       # HTTP 유틸리티
│   ├── analyzer/
│   │   └── sentiment.py        # VADER 감정 분석
│   ├── db/
│   │   ├── models.py           # DB 테이블 정의
│   │   └── writer.py           # DB 저장 (upsert, 중복방지)
│   ├── api/
│   │   └── main.py             # FastAPI 엔드포인트
│   ├── main.py                 # 파이프라인 오케스트레이터
│   └── settings.py             # 환경변수 설정
├── tests/
│   ├── test_collector.py       # 수집 모듈 테스트
│   ├── test_analyzer.py        # 감정분석 테스트
│   └── test_db.py              # DB 테스트
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
docker compose up -d db selenium api

# 파이프라인 수동 실행
docker compose run --rm pipeline
```

### 환경변수 (.env)

```
DATABASE_URL=postgresql://stockmind:stockmind@db:5432/stockmind
YF_MAX_SCROLL=10
YF_MAX_ARTICLES=30
PRICE_PERIOD=5d
PRICE_INTERVAL=1d
USE_REMOTE_WEBDRIVER=false
SELENIUM_REMOTE_URL=http://selenium:4444
```

---

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 서버 상태 확인 |
| GET | `/stocks/{ticker}/prices` | 주가 이력 조회 |
| GET | `/stocks/{ticker}/news` | 뉴스 감정분석 이력 조회 |
| GET | `/stocks/{ticker}/summary` | 날짜별 주가 + 감정 요약 |

### 응답 예시 (/stocks/TSLA/summary)

```json
[
  {
    "ticker": "TSLA",
    "date": "2026-02-27",
    "direction": "down",
    "price_change_pct": -0.1067,
    "article_count": 13,
    "positive_count": 10,
    "negative_count": 3,
    "neutral_count": 0
  }
]
```

Swagger UI: `http://[EC2_HOST]:8000/docs`

---

## CI/CD 파이프라인

### CI (ci.yml)
- **트리거**: PR 생성 시 (→ main)
- **동작**: pytest 자동 실행 (18개 테스트)
- **효과**: 테스트 실패 시 머지 불가

### CD (cd.yml)
두 개의 독립적인 job으로 구성.

**deploy job** (main 머지 시에만 실행)
1. Docker 이미지 빌드
2. AWS ECR에 푸시
3. EC2에 SSH 접속 → 최신 이미지 배포

**pipeline job** (main 머지 시 + 매일 KST 09:00 cron)
1. Actions runner에서 Chromium으로 뉴스 크롤링
2. VADER 감정분석
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
| ECR push 실패 | GitHub Secret 값 오류 | ECR_REPOSITORY Secret 재등록 |
| SSH 접속 타임아웃 | 인바운드 SSH 규칙 제한 | Anywhere(0.0.0.0/0)로 변경 |
| ModuleNotFoundError | import 경로 오류 | 절대경로로 수정 (db.models 등) |

---

## 향후 개발 계획

- [ ] 감정분석 고도화 (VADER → FinBERT)
- [ ] 주가 예측 모델 추가 (LSTM)
- [ ] 알림 시스템 (감정 급변 시 Slack 발송)
- [ ] 대시보드 UI 구축
- [ ] 백테스팅 (감정분석 기반 매매 전략 검증)
