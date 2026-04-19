import logging
from contextlib import contextmanager
from datetime import date
from typing import Generator

from sqlalchemy import create_engine, select, text, and_, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import Base, StockPrice, NewsArticle, MarketIndicator, Fundamental, FearGreed, PredictionLog
from settings import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """
    테이블이 없으면 생성.
    기존 테이블에 누락된 컬럼도 추가 (멱등성 보장).
    """
    Base.metadata.create_all(engine)

    migrations = [
        "ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS ma5  FLOAT",
        "ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS ma20 FLOAT",
        "ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS ma60 FLOAT",
        "ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS rsi  FLOAT",
        "ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS high FLOAT",
        "ALTER TABLE stock_prices ADD COLUMN IF NOT EXISTS low  FLOAT",
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS sentiment_reason TEXT",
        "CREATE TABLE IF NOT EXISTS fear_greed (id SERIAL PRIMARY KEY, date DATE NOT NULL UNIQUE, score FLOAT NOT NULL, rating VARCHAR(20) NOT NULL, created_at TIMESTAMP DEFAULT NOW())",
        "ALTER TABLE stock_prices ALTER COLUMN volume TYPE BIGINT",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            conn.execute(text(sql))
        conn.commit()

    logger.info("[writer] DB 테이블 초기화 완료")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── StockPrice ────────────────────────────────────────────────

def upsert_stock_prices(price_data: list[dict]) -> int:
    """
    주가 데이터를 upsert (ticker+date 중복 시 업데이트).
    MA5, MA20, MA60, RSI 포함.
    반환값: 처리된 행 수
    """
    if not price_data:
        return 0

    rows = []
    seen = set()
    for d in price_data:
        try:
            key = (d["ticker"], d["date"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "ticker":           d["ticker"],
                "date":             date.fromisoformat(d["date"]),
                "open":             d["open"],
                "high":             d.get("high"),
                "low":              d.get("low"),
                "close":            d["close"],
                "volume":           d["volume"],
                "price_change":     d["price_change"],
                "price_change_pct": d["price_change_pct"],
                "direction":        d["direction"],
                "ma5":              d.get("ma5"),
                "ma20":             d.get("ma20"),
                "ma60":             d.get("ma60"),
                "rsi":              d.get("rsi"),
            })
        except (KeyError, ValueError) as e:
            logger.warning(f"[writer] 주가 데이터 변환 오류: {e} → {d}")
            continue

    if not rows:
        return 0

    with get_session() as session:
        stmt = pg_insert(StockPrice).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={
                "open":             stmt.excluded.open,
                "high":             stmt.excluded.high,
                "low":              stmt.excluded.low,
                "close":            stmt.excluded.close,
                "volume":           stmt.excluded.volume,
                "price_change":     stmt.excluded.price_change,
                "price_change_pct": stmt.excluded.price_change_pct,
                "direction":        stmt.excluded.direction,
                "ma5":              stmt.excluded.ma5,
                "ma20":             stmt.excluded.ma20,
                "ma60":             stmt.excluded.ma60,
                "rsi":              stmt.excluded.rsi,
            },
        )
        session.execute(stmt)

    logger.info(f"[writer] 주가 upsert 완료: {len(rows)}건")
    return len(rows)


# ── NewsArticle ───────────────────────────────────────────────

def get_existing_urls(ticker: str) -> set[str]:
    with get_session() as session:
        rows = session.execute(
            select(NewsArticle.url).where(NewsArticle.ticker == ticker)
        ).scalars().all()
    return set(rows)


def insert_articles(ticker: str, articles: list[dict]) -> int:
    """
    감정분석이 완료된 기사 목록을 저장.
    url 중복인 경우 skip (on_conflict_do_nothing).
    sentiment_reason 컬럼 추가 (GPT 분석 이유).
    반환값: 실제 삽입된 행 수
    """
    if not articles:
        return 0

    rows = []
    for a in articles:
        if a.get("error") or not a.get("url"):
            continue
        try:
            rows.append({
                "ticker":           ticker,
                "date":             date.fromisoformat(a["date"]),
                "url":              a["url"],
                "title":            (a.get("title") or "")[:1024],
                "content":          a.get("content") or "",
                "sentiment_label":  a.get("sentiment_label"),
                "sentiment_score":  a.get("sentiment_score"),
                "sentiment_reason": a.get("sentiment_reason"),  # GPT 분석 이유
            })
        except (KeyError, ValueError) as e:
            logger.warning(f"[writer] 기사 데이터 변환 오류: {e} → {a.get('url', '')[:60]}")
            continue

    if not rows:
        return 0

    with get_session() as session:
        stmt = pg_insert(NewsArticle).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
        result = session.execute(stmt)
        inserted = result.rowcount

    logger.info(f"[writer] 기사 insert 완료: {inserted}건 (전체 {len(rows)}건 중)")
    return inserted


# ── FearGreed ────────────────────────────────────────────────

def upsert_fear_greed(fear_greed_data: list[dict]) -> int:
    """
    Fear & Greed Index 데이터 upsert (date 중복 시 업데이트).
    반환값: 처리된 행 수
    """
    if not fear_greed_data:
        return 0

    rows = []
    seen = set()
    for d in fear_greed_data:
        try:
            key = d["date"]
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "date":   date.fromisoformat(d["date"]),
                "score":  d["score"],
                "rating": d["rating"],
            })
        except (KeyError, ValueError) as e:
            logger.warning(f"[writer] Fear&Greed 데이터 변환 오류: {e} → {d}")
            continue

    if not rows:
        return 0

    with get_session() as session:
        stmt = pg_insert(FearGreed).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={
                "score":  stmt.excluded.score,
                "rating": stmt.excluded.rating,
            },
        )
        session.execute(stmt)

    logger.info(f"[writer] Fear&Greed upsert 완료: {len(rows)}건")
    return len(rows)


# ── MarketIndicator ───────────────────────────────────────────

def upsert_market_indicators(market_data: list[dict]) -> int:
    """
    시장 지표 데이터 upsert (ticker+date 중복 시 업데이트).
    KOSPI(^KS11), KOSDAQ(^KQ11), 나스닥(^IXIC), VIX(^VIX).
    반환값: 처리된 행 수
    """
    if not market_data:
        return 0

    rows = []
    seen = set()
    for d in market_data:
        try:
            key = (d["ticker"], d["date"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "ticker":     d["ticker"],
                "date":       date.fromisoformat(d["date"]),
                "close":      d["close"],
                "change_pct": d.get("change_pct"),
            })
        except (KeyError, ValueError) as e:
            logger.warning(f"[writer] 시장 지표 데이터 변환 오류: {e} → {d}")
            continue

    if not rows:
        return 0

    with get_session() as session:
        stmt = pg_insert(MarketIndicator).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={
                "close":      stmt.excluded.close,
                "change_pct": stmt.excluded.change_pct,
            },
        )
        session.execute(stmt)

    logger.info(f"[writer] 시장 지표 upsert 완료: {len(rows)}건")
    return len(rows)


# ── PredictionLog ─────────────────────────────────────────────

def insert_prediction_log(result: dict) -> None:
    """
    앙상블 예측 결과를 prediction_logs 테이블에 저장.
    동일 (ticker, prediction_date)가 이미 있으면 무시.
    """
    row = {
        "ticker":          result["ticker"],
        "prediction_date": date.fromisoformat(result["prediction_date"]),
        "based_on_date":   date.fromisoformat(result["based_on_date"]),
        "direction":       result["direction"],
        "up_probability":  result["up_probability"],
        "proba_a":         result["model_probabilities"]["model_a"],
        "proba_b":         result["model_probabilities"]["model_b"],
        "proba_c":         result["model_probabilities"]["model_c"],
        "threshold_used":  result.get("threshold_used"),
    }
    with get_session() as session:
        stmt = pg_insert(PredictionLog).values([row])
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "prediction_date"])
        session.execute(stmt)

    logger.info(
        f"[writer] 예측 로그 저장: {result['ticker']} "
        f"{result['prediction_date']} → {result['direction']} "
        f"(up_prob={result['up_probability']})"
    )


def update_prediction_actuals(ticker: str, prediction_date: date, actual_direction: str) -> int:
    """
    예측 대상 날짜의 실제 방향을 채우고 is_correct 를 업데이트.
    actual_direction 이 아직 없는 행만 업데이트.
    반환값: 업데이트된 행 수
    """
    with get_session() as session:
        stmt = (
            update(PredictionLog)
            .where(
                and_(
                    PredictionLog.ticker == ticker,
                    PredictionLog.prediction_date == prediction_date,
                    PredictionLog.actual_direction.is_(None),
                )
            )
            .values(
                actual_direction=actual_direction,
                is_correct=(PredictionLog.direction == actual_direction),
            )
        )
        result = session.execute(stmt)
        updated = result.rowcount

    if updated:
        logger.info(
            f"[writer] 예측 정답 업데이트: {ticker} {prediction_date} "
            f"actual={actual_direction} ({updated}건)"
        )
    return updated


# ── Fundamental ───────────────────────────────────────────────

def upsert_fundamentals(fundamental_data: list[dict]) -> int:
    """
    펀더멘털 데이터 upsert (ticker+date 중복 시 업데이트).
    시가총액, PER, PBR.
    반환값: 처리된 행 수
    """
    if not fundamental_data:
        return 0

    rows = []
    for d in fundamental_data:
        try:
            rows.append({
                "ticker":     d["ticker"],
                "date":       date.fromisoformat(d["date"]),
                "market_cap": d.get("market_cap"),
                "per":        d.get("per"),
                "pbr":        d.get("pbr"),
            })
        except (KeyError, ValueError) as e:
            logger.warning(f"[writer] 펀더멘털 데이터 변환 오류: {e} → {d}")
            continue

    if not rows:
        return 0

    with get_session() as session:
        stmt = pg_insert(Fundamental).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={
                "market_cap": stmt.excluded.market_cap,
                "per":        stmt.excluded.per,
                "pbr":        stmt.excluded.pbr,
            },
        )
        session.execute(stmt)

    logger.info(f"[writer] 펀더멘털 upsert 완료: {len(rows)}건")
    return len(rows)
