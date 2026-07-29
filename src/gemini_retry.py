import time
from typing import Callable, TypeVar

from google.genai.errors import APIError

# client.interactions.create() (used by GeminiClassifier/GeminiLetterGenerator)
# raises a DIFFERENT, OpenAI-compat-shaped exception hierarchy than the classic
# google.genai.errors.APIError this module was originally written against.
# Confirmed live on 2026-07-29: every single 429 from this surface has a
# .status_code, not a .code, and isn't an APIError instance at all — so it fell
# straight through the `except APIError` below completely uncaught, meaning
# throttling, backoff, and the quota circuit-breaker never actually engaged
# despite looking correct in unit tests (which only ever mocked the legacy
# google.genai.errors.ClientError). A GitHub Actions run burned real quota on
# hundreds of rapid-fire, un-throttled requests as a result. Import is
# defensive: if this internal path ever moves, we degrade to only catching the
# legacy surface rather than crashing outright.
try:
    from google.genai._gaos.lib.compat_errors import APIStatusError as _CompatAPIStatusError

    _RETRYABLE_EXCEPTION_TYPES: tuple[type[Exception], ...] = (APIError, _CompatAPIStatusError)
except ImportError:
    _RETRYABLE_EXCEPTION_TYPES = (APIError,)

T = TypeVar("T")

DEFAULT_BACKOFF_SCHEDULE = (15, 30, 60, 60, 60)
# The 429 error body says "limit: 20" but that figure is misleading — the
# actual per-model cap, confirmed directly on aistudio.google.com/rate-limit,
# is 5 RPM for gemini-3.5-flash on the free tier. 13s keeps us at ~4.6/min,
# a safety margin below that.
MIN_CALL_INTERVAL_SECONDS = 13.0


class GeminiQuotaExhausted(Exception):
    """All retries were spent on 429s without success. Distinguished from a
    plain APIError so callers processing many postings in a loop (see
    src/orchestrator.py) can tell "per-minute throttling, try the next call"
    apart from "quota is dead for the day, stop calling entirely" — confirmed
    live on 2026-07-29: a GitHub Actions run hit the daily quota wall and
    burned its full 45-minute timeout retrying every remaining ambiguous
    posting for ~5 minutes each instead of failing fast.
    """


class RateLimiter:
    """Enforces a minimum interval between calls, shared across every caller
    holding the same instance. Needed because the Gemini free tier quota is
    shared across every call to a given model, not tracked per-caller —
    per-call reactive retry alone isn't enough when many postings are
    classified back-to-back: confirmed live, a run processing 100+ postings
    with retry-on-429 alone still failed on every single one, because other
    postings kept consuming the quota window while any one posting was
    backing off.
    """

    def __init__(self, min_interval: float = MIN_CALL_INTERVAL_SECONDS, time_fn: Callable[[], float] = time.monotonic):
        self._min_interval = min_interval
        self._time_fn = time_fn
        self._last_call_time: float | None = None

    def wait(self, sleep_fn: Callable[[float], None]) -> None:
        now = self._time_fn()
        if self._last_call_time is not None:
            remaining = self._min_interval - (now - self._last_call_time)
            if remaining > 0:
                sleep_fn(remaining)
        self._last_call_time = self._time_fn()


default_rate_limiter = RateLimiter()


def _status_code(exc: Exception) -> int | None:
    return getattr(exc, "code", None) if isinstance(exc, APIError) else getattr(exc, "status_code", None)


def call_with_retry(
    func: Callable[[], T],
    sleep_fn: Callable[[float], None] = time.sleep,
    max_retries: int = len(DEFAULT_BACKOFF_SCHEDULE),
    rate_limiter: RateLimiter = default_rate_limiter,
) -> T:
    """Calls func(), throttling to stay under the shared rate limit and
    retrying on Gemini free-tier rate limit errors (HTTP 429) with a fixed
    backoff schedule. Any other error propagates immediately — retrying
    wouldn't help.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            sleep_fn(DEFAULT_BACKOFF_SCHEDULE[min(attempt - 1, len(DEFAULT_BACKOFF_SCHEDULE) - 1)])
        rate_limiter.wait(sleep_fn)
        try:
            return func()
        except _RETRYABLE_EXCEPTION_TYPES as exc:
            if _status_code(exc) != 429:
                raise
            last_error = exc

    raise GeminiQuotaExhausted(str(last_error)) from last_error
