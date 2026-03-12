import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# GPT API 응답을 흉내내는 mock 응답 생성 함수
def _mock_response(label: str, score: float, reason: str = "test reason"):
    """OpenAI API 응답 구조를 흉내내는 mock 객체 생성"""
    import json
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "label": label,
        "score": score,
        "reason": reason,
    })
    return mock_response


class TestSentiment:

    @patch("analyzer.sentiment._get_client")
    def test_positive(self, mock_get_client):
        """긍정 뉴스 → positive 반환"""
        mock_get_client.return_value.chat.completions.create.return_value = \
            _mock_response("positive", 0.8)

        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("excellent growth record profit outstanding")
        assert result["label"] in ["positive", "neutral"]
        assert -1.0 <= result["score"] <= 1.0

    @patch("analyzer.sentiment._get_client")
    def test_negative(self, mock_get_client):
        """부정 뉴스 → negative 반환"""
        mock_get_client.return_value.chat.completions.create.return_value = \
            _mock_response("negative", -0.8)

        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("terrible loss bankruptcy failure crisis")
        assert result["label"] in ["negative", "neutral"]
        assert -1.0 <= result["score"] <= 1.0

    def test_empty_string(self):
        """빈 문자열 → neutral, score 0.0 (API 호출 없음)"""
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("")
        assert result["label"] == "neutral"
        assert result["score"] == 0.0

    def test_none_input(self):
        """None 입력 → neutral, score 0.0 (API 호출 없음)"""
        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment(None)
        assert result["label"] == "neutral"
        assert result["score"] == 0.0

    @patch("analyzer.sentiment._get_client")
    def test_score_range(self, mock_get_client):
        """score가 -1.0 ~ 1.0 범위인지 확인"""
        mock_get_client.return_value.chat.completions.create.return_value = \
            _mock_response("neutral", 0.0)

        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("stock market today")
        assert -1.0 <= result["score"] <= 1.0

    @patch("analyzer.sentiment._get_client")
    def test_reason_field_exists(self, mock_get_client):
        """sentiment_reason 필드가 반환되는지 확인"""
        mock_get_client.return_value.chat.completions.create.return_value = \
            _mock_response("positive", 0.8, "Strong earnings report")

        from analyzer.sentiment import analyze_sentiment
        result = analyze_sentiment("profit increased significantly")
        assert "reason" in result
        assert isinstance(result["reason"], str)

    @patch("analyzer.sentiment._get_client")
    def test_analyze_articles_structure(self, mock_get_client):
        """analyze_articles가 sentiment 필드를 추가하는지 확인"""
        mock_get_client.return_value.chat.completions.create.side_effect = [
            _mock_response("positive", 0.8),
            _mock_response("negative", -0.7),
        ]

        from analyzer.sentiment import analyze_articles
        articles = [
            {"url": "http://test.com/1", "title": "Good news", "content": "profit up", "date": "2026-01-01"},
            {"url": "http://test.com/2", "title": "Bad news",  "content": "loss down", "date": "2026-01-01"},
        ]
        results = analyze_articles(articles)
        assert len(results) == 2
        for r in results:
            assert "sentiment_label"  in r
            assert "sentiment_score"  in r
            assert "sentiment_reason" in r
            assert r["sentiment_label"] in ["positive", "negative", "neutral"]

    def test_analyze_articles_empty(self):
        """빈 리스트 입력 시 빈 리스트 반환"""
        from analyzer.sentiment import analyze_articles
        results = analyze_articles([])
        assert results == []
