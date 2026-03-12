import os
import logging
import json
from openai import OpenAI

logger = logging.getLogger(__name__)

# 싱글톤 클라이언트
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


def analyze_sentiment(text: str) -> dict:
    """
    GPT-4o-mini로 금융 뉴스 감정분석.
    지정학적 리스크, 시사 이벤트 등 금융에 간접적으로 영향을 미치는
    맥락까지 고려한 분석 수행.

    반환 예시:
    {
        "label":  "positive",
        "score":  0.8,        # -1.0 ~ 1.0
        "reason": "..."       # 분석 이유
    }
    """
    if not isinstance(text, str) or not text.strip():
        return {"label": "neutral", "score": 0.0, "reason": ""}

    try:
        client = _get_client()
        prompt = f"""You are a financial news sentiment analyst.
Analyze the sentiment of the following news article from the perspective of its impact on stock prices.
Consider not only direct financial metrics but also geopolitical risks, macroeconomic events, and market sentiment.

Respond ONLY in JSON format with no extra text:
{{
  "label": "positive" or "negative" or "neutral",
  "score": float between -1.0 and 1.0,
  "reason": "brief explanation in English (1-2 sentences)"
}}

News:
{text[:2000]}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()

        # JSON 파싱
        result = json.loads(raw)
        label  = result.get("label", "neutral")
        score  = round(float(result.get("score", 0.0)), 4)
        reason = result.get("reason", "")

        # label 유효성 검사
        if label not in ("positive", "negative", "neutral"):
            label = "neutral"
        score = max(-1.0, min(1.0, score))

        return {"label": label, "score": score, "reason": reason}

    except json.JSONDecodeError as e:
        logger.warning(f"[sentiment] JSON 파싱 실패: {e}")
        return {"label": "neutral", "score": 0.0, "reason": ""}
    except Exception as e:
        logger.warning(f"[sentiment] GPT 분석 실패: {e}")
        return {"label": "neutral", "score": 0.0, "reason": ""}


def analyze_articles(articles: list[dict]) -> list[dict]:
    """
    fetch_articles()의 반환값을 받아 각 기사에 sentiment 필드를 추가해 반환.

    입력:
    [{"url": ..., "title": ..., "content": ..., "date": ...}, ...]

    출력:
    [{"url": ..., "title": ..., "content": ..., "date": ...,
      "sentiment_label": "positive",
      "sentiment_score": 0.8,
      "sentiment_reason": "..."}, ...]
    """
    results = []
    for article in articles:
        text = article.get("content") or article.get("title") or ""
        sentiment = analyze_sentiment(text)

        results.append({
            **article,
            "sentiment_label":  sentiment["label"],
            "sentiment_score":  sentiment["score"],
            "sentiment_reason": sentiment["reason"],
        })

    pos = sum(1 for r in results if r["sentiment_label"] == "positive")
    neg = sum(1 for r in results if r["sentiment_label"] == "negative")
    neu = sum(1 for r in results if r["sentiment_label"] == "neutral")
    logger.info(f"[sentiment] 분석 완료 → positive={pos}, negative={neg}, neutral={neu}")

    return results
