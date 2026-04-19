Display a full status summary of the Stockmind Mini project. Use the available tools to gather current state across all dimensions.

Run the following checks IN PARALLEL where possible, then compile results into a single formatted report:

## 1. DB 현황 (PostgreSQL MCP or Bash with docker exec)

Query the database for:
- `stock_prices`: row count and date range per ticker (005930.KS, TSLA)
- `news_articles`: row count per ticker
- `market_indicators`: row count and date range
- `fear_greed`: row count and date range
- `prediction_logs`: if the table exists, last 7 days accuracy (is_correct rate)

Use this SQL:
```sql
SELECT ticker, COUNT(*) as rows, MIN(date) as from_date, MAX(date) as to_date
FROM stock_prices GROUP BY ticker ORDER BY ticker;

SELECT ticker, COUNT(*) as rows FROM news_articles GROUP BY ticker ORDER BY ticker;

SELECT COUNT(*) as rows, MIN(date) as from_date, MAX(date) as to_date FROM fear_greed;

SELECT ticker, COUNT(*) as rows, MIN(date) as from_date, MAX(date) as to_date
FROM market_indicators GROUP BY ticker ORDER BY ticker;

-- prediction_logs (exists only after Phase 1-1)
SELECT ticker,
       COUNT(*) as total_predictions,
       SUM(CASE WHEN is_correct = true THEN 1 ELSE 0 END) as correct,
       ROUND(AVG(CASE WHEN is_correct IS NOT NULL THEN is_correct::int END)::numeric, 3) as accuracy
FROM prediction_logs
WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY ticker;
```

If MCP is not available, use:
```bash
docker exec stockmind-mini-db-1 psql -U stockmind -d stockmind -c "..."
```

## 2. 모델 파일 현황

Check the `models/` directory for the latest model files per ticker:
```bash
ls -la models/ | grep -E "(lstm|xgb|scaler|meta|ensemble)" | sort
```

Extract the most recent date suffix for each model type:
- `{ticker}_lstm_*.pt` → Model A LSTM
- `{ticker}_xgb_*.pkl` → Model A XGBoost
- `{ticker}_b_xgb_*.pkl` → Model B
- `{ticker}_c_xgb_*.pkl` → Model C
- `{ticker}_ensemble_xgb_*.pkl` → Ensemble

## 3. 마지막 GitHub Actions 실행 현황

```bash
gh run list --limit 5 --json conclusion,createdAt,displayTitle,status
```

## 4. 미완성 항목 체크 (CLAUDE.md 기준)

Read `CLAUDE.md` and report which ⬜ items remain incomplete.

---

## Output Format

Print the report in this exact format:

```
# Stockmind Mini — 현재 상태 ($DATE)

## DB 현황
| 테이블 | 종목 | 행 수 | 기간 |
|--------|------|-------|------|
| stock_prices | 005930.KS | ... | ... ~ ... |
| stock_prices | TSLA | ... | ... ~ ... |
| news_articles | 005930.KS | ... | — |
| news_articles | TSLA | ... | — |
| fear_greed | — | ... | ... ~ ... |
| market_indicators | ^KS11 등 4개 | ... | ... ~ ... |

## 예측 성능 (최근 30일)
| 종목 | 예측 횟수 | 정확도 |
|------|----------|--------|
(prediction_logs 없으면 "⬜ prediction_logs 미구현 — Phase 1-1 필요"로 표시)

## 모델 버전
| 종목 | 모델 | 버전 날짜 |
|------|------|----------|
| 005930.KS | LSTM+XGBoost (A) | YYYYMMDD |
...

## GitHub Actions (최근 5회)
| 상태 | 제목 | 일시 |
|------|------|------|
...

## 미완성 항목
(CLAUDE.md의 ⬜ 항목 목록)

## 다음 권장 작업
(현재 상태 기반으로 가장 시급한 1~3가지 작업 제안)
```
