import os
import time
import random
import logging
import datetime as dt
from typing import Iterable, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from collector.http_utils import make_session, http_get, UARotator
from settings import UA_LIST, SELENIUM

logger = logging.getLogger(__name__)


def _get_driver_for_fallback(user_agent: Optional[str] = None) -> webdriver.Remote:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")
    use_remote = os.getenv("USE_REMOTE_WEBDRIVER", "false").lower() == "true"
    if use_remote:
        remote_url = os.getenv("SELENIUM_REMOTE_URL", "http://selenium:4444")
        return webdriver.Remote(command_executor=remote_url, options=opts)
    return webdriver.Chrome(options=opts)


def _extract_title_safely(soup: BeautifulSoup) -> str:
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return og["content"].strip()

    meta_title = soup.find("meta", attrs={"name": "title"})
    if meta_title and meta_title.get("content"):
        return meta_title["content"].strip()

    for sel in ("h1", "header h1", "article h1", "div.caas-title-wrapper h1"):
        h = soup.select_one(sel)
        if h and h.get_text(strip=True):
            return h.get_text(strip=True)

    if soup.title and soup.title.get_text():
        return soup.title.get_text(strip=True)
    return ""


def _extract_content_safely(soup: BeautifulSoup) -> str:
    primary = soup.select("article p, main p, div[data-test-locator='mega'] p")
    if primary:
        return " ".join(p.get_text(strip=True) for p in primary if p.get_text(strip=True))

    for sel in [
        "div.caas-body p",
        "div#article-body p",
        "div[itemprop='articleBody'] p",
        "div[itemprop='articleBody'] div p",
        "section[data-test-locator='mega'] p",
    ]:
        nodes = soup.select(sel)
        if nodes:
            return " ".join(p.get_text(strip=True) for p in nodes if p.get_text(strip=True))

    meta = soup.find("meta", {"name": "description"}) or soup.find("meta", {"property": "og:description"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    return ""


def _parse_date_kst(soup: BeautifulSoup) -> str:
    """기사 발행일을 KST 기준 YYYY-MM-DD 로 반환. 실패 시 오늘 날짜."""
    import pandas as pd

    t = soup.select_one("time[datetime]")
    if t and t.has_attr("datetime"):
        try:
            utc_iso = t["datetime"].replace("Z", "+00:00")
            kst = pd.to_datetime(utc_iso).tz_convert("Asia/Seoul").to_pydatetime()
            return kst.strftime("%Y-%m-%d")
        except Exception:
            pass

    for meta_name in (
        {"property": "article:published_time"},
        {"name": "article:published_time"},
        {"name": "publish-date"},
        {"itemprop": "datePublished"},
    ):
        meta = soup.find("meta", attrs=meta_name)
        if meta and meta.get("content"):
            try:
                utc_iso = meta["content"].replace("Z", "+00:00")
                kst = pd.to_datetime(utc_iso).tz_convert("Asia/Seoul").to_pydatetime()
                return kst.strftime("%Y-%m-%d")
            except Exception:
                continue

    return dt.datetime.now().strftime("%Y-%m-%d")


def fetch_articles(
    urls: Iterable[str],
    ua_mode: str = "round_robin",
    delay_range: tuple = (0.8, 1.6),
    min_len_for_ok: int = 120,
    enable_selenium_fallback: bool = True,
) -> list[dict]:
    """
    URL 목록을 받아 기사 본문을 수집.

    반환 예시:
    [
        {
            "url": "https://...",
            "title": "Tesla reports record...",
            "content": "Tesla Inc. reported...",
            "date": "2024-05-01",
        },
        ...
    ]
    실패한 URL은 error 키를 포함해 반환.
    """
    rotator = UARotator(UA_LIST, ua_mode)
    session = make_session()
    results = []

    for u in urls:
        try:
            resp = http_get(u, session=session, ua_rotator=rotator)
            soup = BeautifulSoup(resp.text, "html.parser")
            content = _extract_content_safely(soup)
            title = _extract_title_safely(soup)
            date_str = _parse_date_kst(soup)

            # 본문이 너무 짧으면 Selenium 폴백 시도
            if enable_selenium_fallback and len(content) < min_len_for_ok and "finance.yahoo.com" in u:
                driver = _get_driver_for_fallback(user_agent=rotator.pick())
                try:
                    driver.set_page_load_timeout(SELENIUM.get("page_load_timeout", 180))
                    driver.get(u)
                    time.sleep(1.5)
                    soup2 = BeautifulSoup(driver.page_source, "html.parser")
                    content2 = _extract_content_safely(soup2)
                    if len(content2) > len(content):
                        content = content2
                        date_str = _parse_date_kst(soup2) or date_str
                        title2 = _extract_title_safely(soup2)
                        if title2:
                            title = title2
                finally:
                    try:
                        driver.quit()
                    except Exception:
                        pass

            results.append({
                "url": u,
                "title": title or "",
                "content": content or "",
                "date": date_str,
            })
            logger.debug(f"[article_fetcher] 수집 완료: {u[:60]}...")

        except Exception as e:
            logger.warning(f"[article_fetcher] 실패: {u[:60]}... → {e}")
            results.append({
                "url": u,
                "title": "",
                "content": "",
                "date": dt.datetime.now().strftime("%Y-%m-%d"),
                "error": str(e),
            })

        time.sleep(random.uniform(*delay_range))

    logger.info(f"[article_fetcher] 총 {len(results)}개 처리 완료")
    return results
