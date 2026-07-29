import pytest
from google.genai.errors import ClientError

from src.gemini_retry import RateLimiter, call_with_retry


def rate_limit_error():
    return ClientError(429, {"error": {"message": "quota exceeded"}})


def fresh_limiter():
    # min_interval=0 isolates retry/backoff behavior from throttling — the
    # rate limiter's own interval logic has dedicated tests further down.
    return RateLimiter(min_interval=0)


def test_returns_result_on_first_success():
    sleeps = []

    result = call_with_retry(lambda: "ok", sleep_fn=sleeps.append, rate_limiter=fresh_limiter())

    assert result == "ok"
    assert sleeps == []


def test_retries_on_429_and_eventually_succeeds():
    sleeps = []
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise rate_limit_error()
        return "ok"

    result = call_with_retry(flaky, sleep_fn=sleeps.append, rate_limiter=fresh_limiter())

    assert result == "ok"
    assert calls["count"] == 3
    assert len(sleeps) == 2


def test_reraises_non_429_errors_immediately_without_retry():
    calls = {"count": 0}

    def always_400():
        calls["count"] += 1
        raise ClientError(400, {"error": {"message": "bad request"}})

    with pytest.raises(ClientError):
        call_with_retry(always_400, sleep_fn=lambda _: None, rate_limiter=fresh_limiter())

    assert calls["count"] == 1


def test_gives_up_after_max_retries_and_raises_last_error():
    calls = {"count": 0}

    def always_429():
        calls["count"] += 1
        raise rate_limit_error()

    with pytest.raises(ClientError):
        call_with_retry(always_429, sleep_fn=lambda _: None, max_retries=3, rate_limiter=fresh_limiter())

    assert calls["count"] == 4


class FakeClock:
    def __init__(self, start=0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_rate_limiter_does_not_wait_on_first_call():
    clock = FakeClock(start=100.0)
    limiter = RateLimiter(min_interval=3.5, time_fn=clock)
    sleeps = []

    limiter.wait(sleep_fn=sleeps.append)

    assert sleeps == []


def test_rate_limiter_waits_remaining_interval_on_immediate_second_call():
    clock = FakeClock(start=100.0)
    limiter = RateLimiter(min_interval=3.5, time_fn=clock)

    limiter.wait(sleep_fn=lambda _: None)
    sleeps = []
    limiter.wait(sleep_fn=sleeps.append)

    assert sleeps == [3.5]


def test_rate_limiter_does_not_wait_if_enough_time_already_elapsed():
    clock = FakeClock(start=100.0)
    limiter = RateLimiter(min_interval=3.5, time_fn=clock)

    limiter.wait(sleep_fn=lambda _: None)
    clock.now += 10
    sleeps = []
    limiter.wait(sleep_fn=sleeps.append)

    assert sleeps == []


def test_rate_limiter_is_shared_across_multiple_call_with_retry_invocations():
    clock = FakeClock(start=0.0)
    limiter = RateLimiter(min_interval=3.5, time_fn=clock)
    sleeps = []

    call_with_retry(lambda: "a", sleep_fn=sleeps.append, rate_limiter=limiter)
    call_with_retry(lambda: "b", sleep_fn=sleeps.append, rate_limiter=limiter)

    assert sleeps == [3.5]
