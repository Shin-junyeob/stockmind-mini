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
- DB 테이블: market_indicators, fundamentals 추가
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

## 현재 상태

```
✅ 주가 수집 (Yahoo Finance API)
✅ 기술적 지표 (MA5, MA20, MA60, RSI)
✅ 시장 지표 (KOSPI, KOSDAQ, 나스닥, VIX)
✅ 뉴스 수집 (Selenium)
✅ 감정분석 (GPT-4o-mini) + 분석 이유 저장
✅ DB 저장 (PostgreSQL 4개 테이블)
✅ FastAPI REST API 서버
✅ Docker 컨테이너화
✅ CI/CD (GitHub Actions)
✅ AWS EC2 배포
✅ 매일 KST 09:00 자동 수집 (cron)
✅ feature → dev → main Git Flow
⏸️ 펀더멘털 수집 (Yahoo Finance 401로 보류)
```

---

## 2단계: 과거 데이터 수집 + 주가 기반 예측모델 (Model A)

**설계 방향**
- 예측모델에 필요한 최소 데이터: 200일치 이상
- 현재 보유 데이터: 약 13일치 → 1회성 backfill 스크립트로 1년치 수집 필요
- 매일 수집 cron은 5d 유지, 과거 데이터는 backfill.py로 1회만 실행

**진행할 것**
```
⬜ backfill.py 작성 (1회성 과거 데이터 수집 스크립트)
   - 주가 1년치 수집
   - 시장 지표 1년치 수집
   - 기술적 지표 자동 계산 포함

⬜ Feature 설계
   - 주가 데이터 (open, close, volume, price_change_pct)
   - 기술적 지표 (MA5, MA20, MA60, RSI)
   - 시장 지표 (KOSPI/NASDAQ, VIX)
   - 차트패턴 파생 feature (골든크로스 등 0/1)

⬜ 모델 선택 및 학습
   - LSTM (시계열 장기의존성 학습)
   - 예측 타겟: 다음날 방향 (up / down / flat)

⬜ 예측 결과 DB 저장
⬜ API 엔드포인트 추가 (/stocks/{ticker}/prediction)
⬜ 예측값을 feature A로 저장
```

**설계 메모**
- 금융 데이터는 비정형이라 단일 모델의 예측 정확도가 낮음 (학계 기준 60~65%면 의미있음)
- 단독 예측보다 여러 모델의 신호를 종합하는 앙상블 방식이 더 신뢰도 높음
- 차트패턴(골든크로스 등)도 규칙 기반 feature로 추가 가능

---

## 3단계: 감정분석 기반 예측모델 (Model B)

**설계 방향**
- 뉴스 감정분석 데이터가 충분히 쌓인 후 진행 (최소 60~90일치)
- 일별 감정점수 평균, 긍정/부정 비율, 감정 추세를 feature로 사용

```
⬜ 감정분석 feature 설계
⬜ 모델 학습 (감정 → 주가 방향 예측)
⬜ 예측값을 feature B로 저장
⬜ 예측 결과 DB 저장
```

---

## 4단계: 앙상블 메타모델 (최종 예측)

**설계 방향**
- 스태킹(Stacking) 방식: 각 모델의 예측값을 새로운 feature로 사용해 메타모델 학습
- 백테스팅으로 각 모델의 실제 정확도를 측정하고, 그 정확도 기반으로 가중치 자동 튜닝
- 예: 주가모델 50% + 감정모델 30% + 기타 20% (백테스팅 결과에 따라 조정)

```
⬜ feature A (주가 기반 예측) +
   feature B (감정 기반 예측) +
   feature C (추가 데이터) 결합
⬜ 가중치 설계 및 백테스팅으로 최적화
⬜ 메타모델 학습
⬜ 최종 예측 결과 DB 저장
⬜ 백테스팅 (예측 정확도 검증, 전략 수정)
```

---

## 5단계: AI Agent

**설계 방향**
- LangGraph로 Agent 구성
- 자연어 질문으로 투자 판단 지원 (알림 시스템 대체)
- GPT API는 감정분석 도구 교체일 뿐, AI Agent와는 다른 개념

```
⬜ LangGraph Agent 구성
⬜ 도구 설계
   - DB 조회 (감정분석, 주가, 예측결과)
   - 실시간 뉴스 검색
   - 기술적 지표 계산
   - 앙상블 예측 결과 조회
⬜ 자연어 질문 대응
   예: "삼성전자 지금 사도 돼?"
       "오늘 테슬라 관련 뉴스 요약해줘"
       "최근 일주일 감정분석 트렌드는?"
```

---

## 단계별 진행 현황

| 단계 | 상태 | 시작일 | 완료일 |
|------|------|--------|--------|
| v1.0 기반 구축 | ✅ 완료 | 2026.02 | 2026.02 |
| v1.1 아키텍처 변경 | ✅ 완료 | 2026.03 | 2026.03 |
| v1.2 데이터 확장 | ✅ 완료 | 2026.03 | 2026.03 |
| 2단계 주가 예측모델 A | 🔄 진행중 | 2026.03 | - |
| 3단계 감정 예측모델 B | ⬜ 대기 | - | - |
| 4단계 앙상블 메타모델 | ⬜ 대기 | - | - |
| 5단계 AI Agent | ⬜ 대기 | - | - |
