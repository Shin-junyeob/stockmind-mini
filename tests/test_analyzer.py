import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSentiment:
    def test_positive(self):
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("excellent growth record profit outstanding")
        assert result["label"] in ["positive", "neutral"]
        assert -1.0 <= result["score"] <= 1.0

    def test_negative(self):
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("terrible loss bankruptcy failure crisis")
        assert result["label"] in ["negative", "neutral"]
        assert -1.0 <= result["score"] <= 1.0

    def test_empty_string(self):
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("")
        assert result["label"] == "neutral"
        assert result["score"] == 0.0

    def test_none_input(self):
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment(None)
        assert result["label"] == "neutral"
        assert result["score"] == 0.0

    def test_score_range(self):
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("stock market today")
        assert -1.0 <= result["score"] <= 1.0

    def test_analyze_articles_structure(self):
        """analyze_articles가 sentiment 필드를 추가하는지 확인"""
        from analyzer.sentiment import analyze_articles
        articles = [
            {"url": "http://test.com/1", "title": "Good news", "content": "profit up", "date": "2026-01-01"},
            {"url": "http://test.com/2", "title": "Bad news", "content": "loss down", "date": "2026-01-01"},
        ]
        results = analyze_articles(articles)
        assert len(results) == 2
        for r in results:
            assert "sentiment_label" in r
            assert "sentiment_score" in r
            assert r["sentiment_label"] in ["positive", "negative", "neutral"]

    def test_analyze_articles_empty(self):
        """빈 리스트 입력 시 빈 리스트 반환"""
        from analyzer.sentiment import analyze_articles
        results = analyze_articles([])
        assert results == []
