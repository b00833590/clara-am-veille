import requests

from src.validation.url_validator import is_url_expired

URL = "https://example.com/job/123"


def test_returns_true_for_404(requests_mock):
    requests_mock.head(URL, status_code=404)

    assert is_url_expired(URL) is True


def test_returns_true_for_410_gone(requests_mock):
    requests_mock.head(URL, status_code=410)

    assert is_url_expired(URL) is True


def test_returns_false_for_200_still_live(requests_mock):
    requests_mock.head(URL, status_code=200)

    assert is_url_expired(URL) is False


def test_falls_back_to_get_when_head_not_allowed(requests_mock):
    requests_mock.head(URL, status_code=405)
    requests_mock.get(URL, status_code=404)

    assert is_url_expired(URL) is True


def test_returns_none_on_network_error_never_marks_expired(requests_mock):
    requests_mock.head(URL, exc=requests.ConnectionError)

    assert is_url_expired(URL) is None


def test_returns_none_on_timeout_never_marks_expired(requests_mock):
    requests_mock.head(URL, exc=requests.Timeout)

    assert is_url_expired(URL) is None


def test_returns_none_for_ambiguous_status_code_like_403(requests_mock):
    # A 403 could mean anti-bot protection on a still-live posting (seen
    # live on BNP Paribas) just as easily as an expired one — never guess.
    requests_mock.head(URL, status_code=403)

    assert is_url_expired(URL) is None
