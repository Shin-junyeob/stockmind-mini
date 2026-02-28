import pytest
import os
import sys

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


class TestWriter:
    def test_init_db(self):
        """DB 연결 및 테이블 생성 테스트"""
        from db.writer import init_db
        try:
            init_db()
        except Exception as e:
            pytest.fail(f"init_db 실패: {e}")

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
