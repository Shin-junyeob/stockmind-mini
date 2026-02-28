import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_

from db.writer import init_db, get_session
from db.models import StockPrice, NewsArticle
from settings import TICKERS

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("[api] 서버 시작")
    yield
    logger.info("[api] 서버 종료")


app = FastAPI(
    title="Stockmind Mini API",
    description="005930.KS / TSLA 주가 및 뉴스 감정분석 조회 API",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Response Schemas ──────────────────────────────────────────

class StockPriceResponse(BaseModel):
    ticker: str
    date: str
    open: float
    close: float
    volume: int
    price_change: float
    price_change_pct: float
    direction: str

    class Config:
        from_attributes = True


class NewsArticleResponse(BaseModel):
    ticker: str
    date: str
    url: str
    title: Optional[str]
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]

    class Config:
        from_attributes = True


class DailySummaryResponse(BaseModel):
    ticker: str
    date: str
    direction: str
    price_change_pct: float
    article_count: int
    positive_count: int
    negative_count: int
    neutral_count: int


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """서버 상태 확인"""
    return {"status": "ok"}


@app.get(
    "/stocks/{ticker}/prices",
    response_model=list[StockPriceResponse],
    summary="주가 이력 조회",
)
def get_stock_prices(
    ticker: str,
    limit: int = Query(default=30, ge=1, le=100, description="조회할 최대 행 수"),
):
    """
    ticker의 일별 주가 데이터를 최신순으로 반환.
    지원 ticker: 005930.KS, TSLA
    """
    _validate_ticker(ticker)
    with get_session() as session:
        rows = session.execute(
            select(StockPrice)
            .where(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.desc())
            .limit(limit)
        ).scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"{ticker} 주가 데이터가 없습니다.")

    return [_price_to_dict(r) for r in rows]


@app.get(
    "/stocks/{ticker}/news",
    response_model=list[NewsArticleResponse],
    summary="뉴스 감정분석 이력 조회",
)
def get_news_articles(
    ticker: str,
    date: Optional[str] = Query(default=None, description="날짜 필터 (YYYY-MM-DD)"),
    sentiment: Optional[str] = Query(default=None, description="감정 필터 (positive/negative/neutral)"),
    limit: int = Query(default=30, ge=1, le=100, description="조회할 최대 행 수"),
):
    """
    ticker의 뉴스 기사 및 감정분석 결과를 최신순으로 반환.
    date, sentiment 필터 사용 가능.
    """
    _validate_ticker(ticker)

    conditions = [NewsArticle.ticker == ticker]
    if date:
        conditions.append(NewsArticle.date == date)
    if sentiment:
        conditions.append(NewsArticle.sentiment_label == sentiment)

    with get_session() as session:
        rows = session.execute(
            select(NewsArticle)
            .where(and_(*conditions))
            .order_by(NewsArticle.date.desc())
            .limit(limit)
        ).scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail="조건에 맞는 기사가 없습니다.")

    return [_article_to_dict(r) for r in rows]


@app.get(
    "/stocks/{ticker}/summary",
    response_model=list[DailySummaryResponse],
    summary="일별 주가 + 감정 요약 조회",
)
def get_daily_summary(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=30, description="조회할 최대 일수"),
):
    """
    날짜별로 주가 등락 방향과 뉴스 감정 분포를 함께 반환.
    파이프라인 동작 확인용 핵심 엔드포인트.
    """
    _validate_ticker(ticker)

    with get_session() as session:
        prices = session.execute(
            select(StockPrice)
            .where(StockPrice.ticker == ticker)
            .order_by(StockPrice.date.desc())
            .limit(limit)
        ).scalars().all()

        if not prices:
            raise HTTPException(status_code=404, detail=f"{ticker} 데이터가 없습니다.")

        summaries = []
        for price in prices:
            articles = session.execute(
                select(NewsArticle).where(
                    and_(
                        NewsArticle.ticker == ticker,
                        NewsArticle.date == price.date,
                    )
                )
            ).scalars().all()

            summaries.append({
                "ticker":           ticker,
                "date":             str(price.date),
                "direction":        price.direction,
                "price_change_pct": price.price_change_pct,
                "article_count":    len(articles),
                "positive_count":   sum(1 for a in articles if a.sentiment_label == "positive"),
                "negative_count":   sum(1 for a in articles if a.sentiment_label == "negative"),
                "neutral_count":    sum(1 for a in articles if a.sentiment_label == "neutral"),
            })

    return summaries


# ── Helpers ───────────────────────────────────────────────────

def _validate_ticker(ticker: str) -> None:
    if ticker not in TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 ticker입니다. 사용 가능: {TICKERS}",
        )


def _price_to_dict(r: StockPrice) -> dict:
    return {
        "ticker":           r.ticker,
        "date":             str(r.date),
        "open":             r.open,
        "close":            r.close,
        "volume":           r.volume,
        "price_change":     r.price_change,
        "price_change_pct": r.price_change_pct,
        "direction":        r.direction,
    }


def _article_to_dict(r: NewsArticle) -> dict:
    return {
        "ticker":          r.ticker,
        "date":            str(r.date),
        "url":             r.url,
        "title":           r.title,
        "sentiment_label": r.sentiment_label,
        "sentiment_score": r.sentiment_score,
    }
