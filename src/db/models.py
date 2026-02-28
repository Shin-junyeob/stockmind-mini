from datetime import date
from sqlalchemy import (
    Column, String, Float, Integer, Date, DateTime, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class StockPrice(Base):
    """
    일별 주가 데이터
    ticker + date 조합으로 중복 방지
    """
    __tablename__ = "stock_prices"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(20), nullable=False)
    date        = Column(Date, nullable=False)
    open        = Column(Float, nullable=False)
    close       = Column(Float, nullable=False)
    volume      = Column(Integer, nullable=False)
    price_change      = Column(Float, nullable=False)
    price_change_pct  = Column(Float, nullable=False)
    direction   = Column(String(10), nullable=False)   # up / down / flat
    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_stock_price_ticker_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<StockPrice ticker={self.ticker} date={self.date} "
            f"direction={self.direction} change={self.price_change_pct}%>"
        )


class NewsArticle(Base):
    """
    수집된 뉴스 기사 + 감정분석 결과
    url 기준으로 중복 방지
    """
    __tablename__ = "news_articles"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    ticker           = Column(String(20), nullable=False)
    date             = Column(Date, nullable=False)
    url              = Column(String(2048), nullable=False, unique=True)
    title            = Column(String(1024), nullable=True)
    content          = Column(String, nullable=True)
    sentiment_label  = Column(String(20), nullable=True)   # positive / negative / neutral
    sentiment_score  = Column(Float, nullable=True)        # -1.0 ~ 1.0
    created_at       = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<NewsArticle ticker={self.ticker} date={self.date} "
            f"sentiment={self.sentiment_label} url={self.url[:40]}...>"
        )
