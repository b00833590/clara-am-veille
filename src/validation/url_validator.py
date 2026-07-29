import requests

# Only these clearly mean "gone". Everything else — including a 403 (seen
# live on BNP Paribas guarding a still-open posting) — is left as "unknown"
# rather than guessed, because a lot of ATS redirect an expired posting to a
# generic "position closed" page that still returns 200; a naive status-code
# check can't see that distinction, and it's safer to under-detect expiry
# than to ever discard a posting that's actually still live.
_DEAD_STATUS_CODES = {404, 410}
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def is_url_expired(url: str, session: requests.Session | None = None, timeout: float = 15.0) -> bool | None:
    """True if the URL is confirmed gone, False if it still resolves,
    None if the check was inconclusive (network error, timeout, or an
    ambiguous status code) — callers must never treat None as expired.
    """
    session = session or requests
    try:
        response = session.head(url, timeout=timeout, allow_redirects=True, headers=_HEADERS)
        if response.status_code == 405:
            response = session.get(url, timeout=timeout, allow_redirects=True, headers=_HEADERS)
    except requests.RequestException:
        return None

    if response.status_code in _DEAD_STATUS_CODES:
        return True
    if response.status_code == 200:
        return False
    return None
