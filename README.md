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
Docker Pipeline
├── 주가 수집       (Yahoo Finance API)
├── 뉴스 링크 수집  (Selenium + Yahoo Finance)
├── 기사 본문 수집  (HTTP + Selenium fallback)
├── 감정 분석       (VADER)
└── DB 저장         (PostgreSQL)
    ↓
FastAPI (EC2 상주)
    ↓
API 응답
```

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
│   │   ├── yahoo_scraper.py    # 뉴스 링크 수집 (Selenium)
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
│       └── cd.yml              # main 머지 시 자동 배포
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
    "date": "2026-02-26",
    "direction": "down",
    "price_change_pct": -1.4092,
    "article_count": 19,
    "positive_count": 13,
    "negative_count": 4,
    "neutral_count": 2
  }
]
```

Swagger UI: `http://localhost:8000/docs`

---

## CI/CD 파이프라인

### CI (ci.yml)
- **트리거**: PR 생성 시
- **동작**: pytest 자동 실행 (18개 테스트)
- **효과**: 테스트 실패 시 머지 불가

### CD (cd.yml)
- **트리거 1**: main 브랜치 머지 시 → 즉시 배포
- **트리거 2**: 매일 KST 09:00 (cron) → 파이프라인 자동 실행
- **동작**:
  1. Docker 이미지 빌드
  2. AWS ECR에 푸시
  3. EC2에 SSH 접속 → 최신 이미지 배포
  4. 파이프라인 실행 (수집 + 분석 + 저장)

```
개발 흐름:
로컬 작업 → PR → CI 테스트 통과 → 머지 → CD 자동 배포
```

---

## 트러블슈팅 기록

| 문제 | 원인 | 해결 |
|------|------|------|
| yfinance Docker 내부 오류 | yfinance 내부 파싱 이슈 | requests로 Yahoo Finance API 직접 호출 |
| EC2 패키지 설치 타임아웃 | 아웃바운드 보안그룹 미설정 | 아웃바운드 All traffic 허용 |
| ECR push 실패 | GitHub Secret 값 오류 | ECR_REPOSITORY Secret 재등록 |
| SSH 접속 타임아웃 | 인바운드 SSH 규칙 My IP 제한 | Anywhere(0.0.0.0/0)로 변경 |
| ModuleNotFoundError | import 경로 오류 | 절대경로로 수정 (db.models 등) |

---

## 향후 개발 계획

- [ ] GitHub Actions runner에서 크롤링 실행 (EC2 메모리 부담 제거)
- [ ] 감정분석 고도화 (VADER → FinBERT)
- [ ] 주가 예측 모델 추가 (LSTM)
- [ ] 알림 시스템 (감정 급변 시 Slack 발송)
- [ ] 대시보드 UI 구축
