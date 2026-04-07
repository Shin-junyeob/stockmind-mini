from datetime import date
from sqlalchemy import (
    Column, String, Float, Integer, Date, DateTime, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class StockPrice(Base):
    """
    일별 주가 데이터 + 기술적 지표
    ticker + date 조합으로 중복 방지
    """
    __tablename__ = "stock_prices"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    ticker            = Column(String(20), nullable=False)
    date              = Column(Date, nullable=False)
    open              = Column(Float, nullable=False)
    high              = Column(Float, nullable=True)   # 당일 최고가
    low               = Column(Float, nullable=True)   # 당일 최저가
    close             = Column(Float, nullable=False)
    volume            = Column(Integer, nullable=False)
    price_change      = Column(Float, nullable=False)
    price_change_pct  = Column(Float, nullable=False)
    direction         = Column(String(10), nullable=False)   # up / down / flat

    # 기술적 지표 (데이터 누적 후 계산, 초기엔 None)
    ma5               = Column(Float, nullable=True)   # 5일 이동평균
    ma20              = Column(Float, nullable=True)   # 20일 이동평균
    ma60              = Column(Float, nullable=True)   # 60일 이동평균
    rsi               = Column(Float, nullable=True)   # RSI (0 ~ 100)

    created_at        = Column(DateTime, server_default=func.now())

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
    sentiment_label  = Column(String(20), nullable=True)    # positive / negative / neutral
    sentiment_score  = Column(Float, nullable=True)         # -1.0 ~ 1.0
    sentiment_reason = Column(String, nullable=True)        # GPT 분석 이유
    created_at       = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<NewsArticle ticker={self.ticker} date={self.date} "
            f"sentiment={self.sentiment_label} url={self.url[:40]}...>"
        )


class FearGreed(Base):
    """
    CNN Fear & Greed Index 일별 데이터
    date 기준으로 중복 방지
    """
    __tablename__ = "fear_greed"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    date       = Column(Date, nullable=False, unique=True)
    score      = Column(Float, nullable=False)          # 0 ~ 100
    rating     = Column(String(20), nullable=False)     # extreme fear ~ extreme greed
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<FearGreed date={self.date} score={self.score} rating={self.rating}>"


class MarketIndicator(Base):
    """
    시장 지표 (KOSPI, KOSDAQ, 나스닥, VIX)
    ticker + date 조합으로 중복 방지
    """
    __tablename__ = "market_indicators"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(20), nullable=False)   # ^KS11, ^KQ11, ^IXIC, ^VIX
    date        = Column(Date, nullable=False)
    close       = Column(Float, nullable=False)
    change_pct  = Column(Float, nullable=True)         # 전일 대비 등락률
    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_market_indicator_ticker_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketIndicator ticker={self.ticker} date={self.date} "
            f"close={self.close} change={self.change_pct}%>"
        )


class Fundamental(Base):
    """
    기업 펀더멘털 데이터 (시가총액, PER, PBR)
    ticker + date 조합으로 중복 방지
    """
    __tablename__ = "fundamentals"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(20), nullable=False)
    date        = Column(Date, nullable=False)
    market_cap  = Column(Float, nullable=True)   # 시가총액
    per         = Column(Float, nullable=True)   # PER
    pbr         = Column(Float, nullable=True)   # PBR
    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_fundamental_ticker_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Fundamental ticker={self.ticker} date={self.date} "
            f"market_cap={self.market_cap} PER={self.per} PBR={self.pbr}>"
        )
