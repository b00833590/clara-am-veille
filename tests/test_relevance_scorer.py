from datetime import datetime, timedelta, timezone

from src.scoring.relevance_scorer import score_posting

NOW = datetime(2026, 7, 22, 12, 0, 0, tzinfo=timezone.utc)


def make_posting(**overrides):
    defaults = dict(
        category="A",
        location_priority=1,
        to_verify=False,
        classification_reason="Poste d'analyste en gestion de portefeuille.",
        detected_at=NOW.isoformat(),
        status="Nouvelle",
    )
    defaults.update(overrides)
    return defaults


def test_category_a_scores_higher_than_b_which_scores_higher_than_n():
    score_a = score_posting(make_posting(category="A")).score
    score_b = score_posting(make_posting(category="B")).score
    score_n = score_posting(make_posting(category="N")).score

    assert score_a > score_b > score_n
    assert score_n == 0


def test_paris_location_scores_higher_than_farther_locations():
    score_paris = score_posting(make_posting(location_priority=1)).score
    score_london = score_posting(make_posting(location_priority=2)).score
    score_other_europe = score_posting(make_posting(location_priority=3)).score
    score_elsewhere = score_posting(make_posting(location_priority=4)).score

    assert score_paris > score_london > score_other_europe > score_elsewhere


def test_to_verify_lowers_the_score():
    confident = score_posting(make_posting(to_verify=False)).score
    uncertain = score_posting(make_posting(to_verify=True)).score

    assert uncertain < confident


def test_missing_classification_reason_lowers_the_score():
    with_reason = score_posting(make_posting(classification_reason="Une bonne raison.")).score
    without_reason = score_posting(make_posting(classification_reason="")).score

    assert without_reason < with_reason


def test_fresher_posting_scores_higher_than_stale_one():
    fresh = score_posting(make_posting(detected_at=NOW.isoformat()), now=NOW).score
    stale = score_posting(make_posting(detected_at=(NOW - timedelta(days=30)).isoformat()), now=NOW).score

    assert fresh > stale


def test_expired_status_caps_the_score_low_regardless_of_other_factors():
    result = score_posting(make_posting(category="A", location_priority=1, status="Expirée"))

    assert result.score <= 10


def test_score_is_always_within_0_and_100():
    for category in ("A", "B", "N", None):
        for location_priority in (1, 2, 3, 4, None):
            result = score_posting(make_posting(category=category, location_priority=location_priority))
            assert 0 <= result.score <= 100


def test_justification_mentions_the_contributing_factors():
    result = score_posting(make_posting(category="A", location_priority=1, to_verify=True))

    assert "métier" in result.justification.lower() or "catégorie" in result.justification.lower()
    assert "vérifier" in result.justification.lower()


def test_unknown_category_scores_zero():
    assert score_posting(make_posting(category=None)).score == 0
