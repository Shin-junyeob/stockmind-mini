import logging
from contextlib import contextmanager
from datetime import date
from typing import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import Base, StockPrice, NewsArticle
from settings import DATABASE_URL

logger = logging.getLogger(__name__)

# 엔진 / 세션 팩토리 (모듈 로드 시 1회 생성)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """테이블이 없으면 생성. 서버 최초 실행 시 호출."""
    Base.metadata.create_all(engine)
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
            },
        )
        session.execute(stmt)

    logger.info(f"[writer] 주가 upsert 완료: {len(rows)}건")
    return len(rows)


# ── NewsArticle ───────────────────────────────────────────────

def get_existing_urls(ticker: str) -> set[str]:
    """
    DB에 이미 저장된 URL 집합 반환.
    yahoo_scraper의 stop_urls로 전달해 중복 수집 방지.
    """
    with get_session() as session:
        rows = session.execute(
            select(NewsArticle.url).where(NewsArticle.ticker == ticker)
        ).scalars().all()
    return set(rows)


def insert_articles(ticker: str, articles: list[dict]) -> int:
    """
    감정분석이 완료된 기사 목록을 저장.
    url 중복인 경우 skip (on_conflict_do_nothing).
    반환값: 실제 삽입된 행 수
    """
    if not articles:
        return 0

    rows = []
    for a in articles:
        # error 키가 있는 실패 항목은 저장하지 않음
        if a.get("error") or not a.get("url"):
            continue
        try:
            rows.append({
                "ticker":          ticker,
                "date":            date.fromisoformat(a["date"]),
                "url":             a["url"],
                "title":           (a.get("title") or "")[:1024],
                "content":         a.get("content") or "",
                "sentiment_label": a.get("sentiment_label"),
                "sentiment_score": a.get("sentiment_score"),
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
