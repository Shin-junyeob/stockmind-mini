import logging
from contextlib import contextmanager
from datetime import date
from typing import Generator

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import Base, StockPrice, NewsArticle, MarketIndicator, Fundamental
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
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS sentiment_reason TEXT",
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
    for d in price_data:
        try:
            rows.append({
                "ticker":           d["ticker"],
                "date":             date.fromisoformat(d["date"]),
                "open":             d["open"],
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
    for d in market_data:
        try:
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
