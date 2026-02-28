import logging
import sys

from settings import TICKERS, YF_MAX_SCROLL, YF_MAX_ARTICLES
from collector.price_fetcher import fetch_price
from collector.yahoo_scraper import collect_yahoo_links
from collector.article_fetcher import fetch_articles
from analyzer.sentiment import analyze_articles
from db.writer import init_db, upsert_stock_prices, insert_articles, get_existing_urls

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_pipeline(tickers: list[str] = TICKERS) -> None:
    """
    전체 파이프라인 실행:
    1. DB 초기화
    2. ticker별로:
       a. 주가 수집 → DB upsert
       b. 뉴스 링크 수집 (기존 URL 제외)
       c. 기사 본문 수집
       d. 감정 분석
       e. DB insert
    """
    logger.info(f"=== 파이프라인 시작 | tickers={tickers} ===")
    init_db()

    for ticker in tickers:
        logger.info(f"--- [{ticker}] 처리 시작 ---")

        # ── 1. 주가 수집 ──────────────────────────────────────
        logger.info(f"[{ticker}] 주가 수집 중...")
        price_data = fetch_price(ticker)
        if price_data:
            upsert_stock_prices(price_data)
        else:
            logger.warning(f"[{ticker}] 주가 데이터 없음, 스킵")

        # ── 2. 뉴스 링크 수집 ────────────────────────────────
        logger.info(f"[{ticker}] 뉴스 링크 수집 중...")
        stop_urls = get_existing_urls(ticker)
        logger.info(f"[{ticker}] 기존 저장 URL {len(stop_urls)}개 → 중복 스킵")

        links = collect_yahoo_links(
            ticker=ticker,
            max_scroll=YF_MAX_SCROLL,
            max_articles=YF_MAX_ARTICLES,
            stop_urls=stop_urls,
        )

        if not links:
            logger.warning(f"[{ticker}] 수집된 링크 없음, 스킵")
            continue

        # ── 3. 기사 본문 수집 ────────────────────────────────
        logger.info(f"[{ticker}] 기사 본문 수집 중... ({len(links)}개)")
        articles = fetch_articles(links)

        # ── 4. 감정 분석 ─────────────────────────────────────
        logger.info(f"[{ticker}] 감정 분석 중...")
        analyzed = analyze_articles(articles)

        # ── 5. DB 저장 ───────────────────────────────────────
        inserted = insert_articles(ticker, analyzed)
        logger.info(f"[{ticker}] DB 저장 완료: {inserted}건")

        logger.info(f"--- [{ticker}] 처리 완료 ---")

    logger.info("=== 파이프라인 종료 ===")


if __name__ == "__main__":
    run_pipeline()
