# outputs/

CC가 생성한 분석 결과물, 리포트, 검토 보고서를 저장하는 디렉토리.

## 저장 대상

| 파일 종류 | 예시 파일명 |
|----------|------------|
| leakage-check 결과 | `leakage-check_YYYYMMDD.md` |
| 백테스팅 결과 요약 | `backtest_{ticker}_YYYYMMDD.md` |
| senior-dev-validator 검토 보고서 | `review_{기능명}_YYYYMMDD.md` |
| 임계값 튜닝 결과 | `threshold_tune_{ticker}_YYYYMMDD.md` |

## 파일 네이밍

```
{종류}_{대상}_{YYYYMMDD}.md
예: leakage-check_ensemble_20260419.md
```

## 주의

- 모델 파일(*.pt, *.pkl)은 `models/`에 저장 (여기 아님)
- 대용량 결과 데이터는 gitignore 처리 필요
