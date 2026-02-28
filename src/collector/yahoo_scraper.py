import os
import time
import random
import logging
from typing import List, Set, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

from settings import SELENIUM, UA_LIST, YF_MAX_SCROLL, YF_MAX_ARTICLES

logger = logging.getLogger(__name__)

# Yahoo Finance 뉴스 기사 선택자 (메인 + 폴백)
YF_STORY_SEL = "section[data-testid='storyitem']"
YF_STORY_FALLBACKS = [
    "li.js-stream-content",
    "div.caas-content-wrapper article a",
    "div.caas-content-wrapper a",
]


def _get_driver(options: Options) -> webdriver.Remote:
    use_remote = os.getenv("USE_REMOTE_WEBDRIVER", "false").lower() == "true"
    if use_remote:
        remote_url = os.getenv("SELENIUM_REMOTE_URL", "http://selenium:4444")
        return webdriver.Remote(command_executor=remote_url, options=options)
    return webdriver.Chrome(options=options)


def _build_chrome_options(user_agent: Optional[str] = None) -> Options:
    opts = Options()
    if SELENIUM.get("headless", True):
        opts.add_argument("--headless=new")
    if SELENIUM.get("disable_gpu", True):
        opts.add_argument("--disable-gpu")
    w, h = SELENIUM.get("window_size", (1920, 1080))
    opts.add_argument(f"--window-size={w}x{h}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--blink-settings=imagesEnabled=false")
    opts.add_experimental_option(
        "prefs",
        {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.default_content_setting_values.notifications": 2,
        },
    )
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")
    return opts


def _normalize_url(href: str) -> Optional[str]:
    if not href:
        return None
    url = href if href.startswith("http") else f"https://finance.yahoo.com{href}"
    return url if "/news/" in url else None


def _scroll_until_stable(driver, max_round: int, pause: float, stable_need: int) -> None:
    last_height = driver.execute_script("return document.body.scrollHeight")
    stable_rounds = 0
    for _ in range(max_round):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            stable_rounds += 1
            if stable_rounds >= stable_need:
                break
        else:
            stable_rounds = 0
            last_height = new_height


def _dismiss_consent(driver) -> None:
    texts = ["Accept", "I agree", "동의", "허용"]
    try:
        for t in texts:
            elems = driver.find_elements(By.XPATH, f"//button[contains(., '{t}')]")
            for e in elems:
                try:
                    e.click()
                    time.sleep(0.5)
                    return
                except (ElementClickInterceptedException, Exception):
                    pass
    except NoSuchElementException:
        pass


def collect_yahoo_links(
    ticker: str,
    max_scroll: int = YF_MAX_SCROLL,
    max_articles: int = YF_MAX_ARTICLES,
    stop_urls: Optional[Set[str]] = None,
    user_agent: Optional[str] = None,
) -> List[str]:
    """
    Yahoo Finance에서 ticker 뉴스 링크를 수집.
    - stop_urls: 이미 DB에 저장된 URL 집합 → 중복 수집 방지
    - max_articles: 최대 수집 기사 수 (이전 200 → 30으로 축소)
    """
    stop_urls = stop_urls or set()
    url = f"https://finance.yahoo.com/quote/{ticker}/news?p={ticker}"
    options = _build_chrome_options(user_agent=user_agent or random.choice(UA_LIST))
    driver = _get_driver(options)

    try:
        driver.set_page_load_timeout(SELENIUM.get("page_load_timeout", 180))
        driver.get(url)

        try:
            _dismiss_consent(driver)
        except Exception:
            pass

        _scroll_until_stable(
            driver,
            max_round=max_scroll,
            pause=SELENIUM.get("scroll_pause", 1.6),
            stable_need=SELENIUM.get("max_stable_rounds", 2),
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        blocks = soup.select(YF_STORY_SEL)

        if not blocks:
            for sel in YF_STORY_FALLBACKS:
                blocks = soup.select(sel)
                if blocks:
                    break

        links: List[str] = []
        seen: Set[str] = set()

        for sec in blocks:
            if len(links) >= max_articles:
                break
            a = sec.find("a") if hasattr(sec, "find") else None
            if a is None and hasattr(sec, "get"):
                a = sec
            href = a.get("href") if a else None
            u = _normalize_url(href)

            if not u or u in seen or u in stop_urls:
                continue
            seen.add(u)
            links.append(u)

        logger.info(f"[yahoo_scraper] {ticker} 링크 {len(links)}개 수집")
        return links

    finally:
        try:
            driver.quit()
        except Exception:
            pass
