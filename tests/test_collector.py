import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestPriceFetcher:
    def test_period_to_days_days(self):
        from collector.price_fetcher import _period_to_days
        assert _period_to_days("5d") == 5

    def test_period_to_days_month(self):
        from collector.price_fetcher import _period_to_days
        assert _period_to_days("1mo") == 30

    def test_period_to_days_three_months(self):
        from collector.price_fetcher import _period_to_days
        assert _period_to_days("3mo") == 90

    def test_period_to_days_default(self):
        from collector.price_fetcher import _period_to_days
        assert _period_to_days("invalid") == 7

    def test_fetch_price_returns_list(self):
        """fetch_price가 list를 반환하는지 확인 (실제 API 호출 없이 구조만 확인)"""
        from collector.price_fetcher import fetch_price
        result = fetch_price("INVALID_TICKER_12345")
        assert isinstance(result, list)

    def test_fetch_all_prices_returns_dict(self):
        """fetch_all_prices가 dict를 반환하는지 확인"""
        from collector.price_fetcher import fetch_all_prices
        from settings import TICKERS
        result = fetch_all_prices()
        assert isinstance(result, dict)
        for ticker in TICKERS:
            assert ticker in result
