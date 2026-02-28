import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# 싱글톤 analyzer (매 호출마다 재생성 방지)
_analyzer = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def analyze_sentiment(text: str) -> dict:
    """
    텍스트를 받아 VADER 감정분석 결과를 반환.

    반환 예시:
    {
        "label": "positive",   # positive / negative / neutral
        "score": 0.82,         # compound score (-1.0 ~ 1.0)
    }

    compound score 기준:
        >= 0.05  → positive
        <= -0.05 → negative
        그 외     → neutral
    """
    if not isinstance(text, str) or not text.strip():
        return {"label": "neutral", "score": 0.0}

    try:
        scores = _get_analyzer().polarity_scores(text[:1000])  # 너무 긴 텍스트 방지
        compound = round(scores["compound"], 4)

        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return {"label": label, "score": compound}

    except Exception as e:
        logger.warning(f"[sentiment] 분석 실패: {e}")
        return {"label": "neutral", "score": 0.0}


def analyze_articles(articles: list[dict]) -> list[dict]:
    """
    fetch_articles()의 반환값을 받아 각 기사에 sentiment 필드를 추가해 반환.

    입력:
    [{"url": ..., "title": ..., "content": ..., "date": ...}, ...]

    출력:
    [{"url": ..., "title": ..., "content": ..., "date": ...,
      "sentiment_label": "positive", "sentiment_score": 0.82}, ...]
    """
    results = []
    for article in articles:
        # content가 있으면 content 기준, 없으면 title 기준으로 분석
        text = article.get("content") or article.get("title") or ""
        sentiment = analyze_sentiment(text)

        results.append({
            **article,
            "sentiment_label": sentiment["label"],
            "sentiment_score": sentiment["score"],
        })

    pos = sum(1 for r in results if r["sentiment_label"] == "positive")
    neg = sum(1 for r in results if r["sentiment_label"] == "negative")
    neu = sum(1 for r in results if r["sentiment_label"] == "neutral")
    logger.info(f"[sentiment] 분석 완료 → positive={pos}, negative={neg}, neutral={neu}")

    return results
