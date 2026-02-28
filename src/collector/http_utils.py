import random
from itertools import cycle
from typing import Iterable, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from settings import UA_LIST, ACCEPT_LANGUAGE, REQUEST_TIMEOUT, TOTAL_RETRY, BACKOFF_FACTOR


class UARotator:
    def __init__(self, ua_list: Optional[List[str]] = None, mode: str = "round_robin"):
        self.ua_list = ua_list or UA_LIST
        self.mode = mode
        self._cycle = cycle(self.ua_list)

    def pick(self) -> str:
        if self.mode == "random":
            return random.choice(self.ua_list)
        return next(self._cycle)


def make_session(
    total_retry: int = TOTAL_RETRY,
    backoff_factor: float = BACKOFF_FACTOR,
) -> requests.Session:
    s = requests.Session()
    r = Retry(
        total=total_retry,
        read=total_retry,
        connect=total_retry,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD", "OPTIONS"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=r, pool_connections=10, pool_maxsize=30)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def http_get(
    url: str,
    session: requests.Session,
    ua_rotator: UARotator,
    **kwargs,
) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", ua_rotator.pick())
    headers.setdefault("Accept-Language", ACCEPT_LANGUAGE)
    headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return session.get(url, headers=headers, timeout=timeout, **kwargs)
