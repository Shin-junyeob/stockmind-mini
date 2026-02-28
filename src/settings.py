import os
from dotenv import load_dotenv

load_dotenv()

# ── 대상 Ticker ───────────────────────────────────────────────
TICKERS: list[str] = ["005930.KS", "TSLA"]

# ── 경로 ─────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.getenv("STOCKMIND_DATA_DIR", os.path.join(BASE_DIR, "data"))

# ── DB ────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://stockmind:stockmind@localhost:5432/stockmind",
)

# ── 크롤링 ────────────────────────────────────────────────────
UA_LIST: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

ACCEPT_LANGUAGE: str = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
REQUEST_TIMEOUT: int = 15
TOTAL_RETRY: int = 3
BACKOFF_FACTOR: float = 0.8

# ── Selenium ──────────────────────────────────────────────────
SELENIUM: dict = {
    "headless": True,
    "disable_gpu": True,
    "window_size": (1920, 1080),
    "page_load_timeout": 180,
    "scroll_pause": 1.6,
    "max_stable_rounds": 2,
}

YF_MAX_SCROLL: int = int(os.getenv("YF_MAX_SCROLL", "10"))       # 이전 20 → 10으로 축소
YF_MAX_ARTICLES: int = int(os.getenv("YF_MAX_ARTICLES", "30"))   # 이전 200 → 30으로 축소

# ── 주가 수집 ─────────────────────────────────────────────────
PRICE_PERIOD: str = os.getenv("PRICE_PERIOD", "5d")   # yfinance 조회 기간
PRICE_INTERVAL: str = os.getenv("PRICE_INTERVAL", "1d")

# ── API ───────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))


