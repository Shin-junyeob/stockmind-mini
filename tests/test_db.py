import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://stockmind:stockmind@localhost:5432/stockmind"
)


class TestModels:
    def test_stock_price_repr(self):
        from db.models import StockPrice
        from datetime import date
        sp = StockPrice(
            ticker="TSLA",
            date=date(2026, 1, 1),
            direction="up",
            price_change_pct=1.5,
        )
        assert "TSLA" in repr(sp)
        assert "up" in repr(sp)

    def test_news_article_repr(self):
        from db.models import NewsArticle
        from datetime import date
        na = NewsArticle(
            ticker="TSLA",
            date=date(2026, 1, 1),
            url="https://finance.yahoo.com/news/test",
            sentiment_label="positive",
        )
        assert "TSLA" in repr(na)
        assert "positive" in repr(na)

    def test_market_indicator_repr(self):
        """MarketIndicator repr 테스트"""
        from db.models import MarketIndicator
        from datetime import date
        mi = MarketIndicator(
            ticker="^KS11",
            date=date(2026, 1, 1),
            close=2500.0,
            change_pct=0.5,
        )
        assert "^KS11" in repr(mi)
        assert "2500.0" in repr(mi)

    def test_fundamental_repr(self):
        """Fundamental repr 테스트"""
        from db.models import Fundamental
        from datetime import date
        f = Fundamental(
            ticker="TSLA",
            date=date(2026, 1, 1),
            market_cap=1000000000.0,
            per=50.0,
            pbr=10.0,
        )
        assert "TSLA" in repr(f)
        assert "50.0" in repr(f)


class TestWriter:
    @patch("db.writer.Base.metadata.create_all")
    def test_init_db(self, mock_create_all):
        """init_db() 함수가 오류 없이 실행되는지 테스트 (DB 연결 mock)"""
        from db.writer import init_db
        try:
            init_db()
        except Exception as e:
            pytest.fail(f"init_db 실패: {e}")
        mock_create_all.assert_called_once()

    def test_upsert_empty_list(self):
        """빈 리스트 upsert 시 0 반환"""
        from db.writer import upsert_stock_prices
        result = upsert_stock_prices([])
        assert result == 0

    def test_insert_empty_list(self):
        """빈 리스트 insert 시 0 반환"""
        from db.writer import insert_articles
        result = insert_articles("TSLA", [])
        assert result == 0

    def test_upsert_market_indicators_empty(self):
        """빈 리스트 market indicator upsert 시 0 반환"""
        from db.writer import upsert_market_indicators
        result = upsert_market_indicators([])
        assert result == 0

    def test_upsert_fundamentals_empty(self):
        """빈 리스트 fundamental upsert 시 0 반환"""
        from db.writer import upsert_fundamentals
        result = upsert_fundamentals([])
        assert result == 0
