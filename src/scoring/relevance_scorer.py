from dataclasses import dataclass
from datetime import datetime, timezone

# Deterministic, rule-based scoring — no LLM call, consistent with the
# quota-reduction work already done on classification (HybridClassifier).
# Weights reflect the classification prompt's own priorities: category is the
# dominant factor (an A posting is what actually matters), location is a
# secondary tie-breaker (never an exclusion signal, per src/location_priority.py),
# and the rest are confidence/freshness adjustments.
CATEGORY_BASE_SCORE = {"A": 80, "B": 45, "N": 0}
LOCATION_BONUS = {1: 15, 2: 10, 3: 5, 4: 0}
TO_VERIFY_PENALTY = 5
MISSING_REASON_PENALTY = 5
EXPIRED_SCORE_CEILING = 10


@dataclass
class ScoreResult:
    score: int
    justification: str


def score_posting(posting: dict, now: datetime | None = None) -> ScoreResult:
    now = now or datetime.now(timezone.utc)

    category = posting.get("category")
    base = CATEGORY_BASE_SCORE.get(category, 0)

    if base == 0:
        # N ("Hors sujet") or an unrecognized category — location, freshness,
        # etc. are meaningless for a posting that isn't relevant to begin
        # with, so it scores a flat 0 rather than picking up bonuses from
        # factors that don't matter here.
        return ScoreResult(
            score=0,
            justification=f"Catégorie/métier ({category or 'non classé'}) : hors périmètre, score nul.",
        )

    reasons: list[str] = [f"Catégorie/métier ({category}) : +{base}"]
    score = base

    location_priority = posting.get("location_priority") or 4
    location_bonus = LOCATION_BONUS.get(location_priority, 0)
    if location_bonus:
        reasons.append(f"Localisation (priorité {location_priority}) : +{location_bonus}")
    score += location_bonus

    freshness_bonus = _freshness_bonus(posting.get("detected_at"), now)
    if freshness_bonus:
        reasons.append(f"Fraîcheur de publication : +{freshness_bonus}")
    score += freshness_bonus

    if posting.get("to_verify"):
        reasons.append(f"Classification à vérifier : -{TO_VERIFY_PENALTY}")
        score -= TO_VERIFY_PENALTY

    if not posting.get("classification_reason"):
        reasons.append(f"Raison de classification absente : -{MISSING_REASON_PENALTY}")
        score -= MISSING_REASON_PENALTY

    score = max(0, min(100, score))

    if posting.get("status") == "Expirée":
        reasons.append(f"Offre expirée : plafonné à {EXPIRED_SCORE_CEILING}")
        score = min(score, EXPIRED_SCORE_CEILING)

    return ScoreResult(score=score, justification=" ; ".join(reasons))


def _freshness_bonus(detected_at, now: datetime) -> int:
    if not detected_at:
        return 0
    try:
        parsed = datetime.fromisoformat(detected_at) if isinstance(detected_at, str) else detected_at
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0

    age_days = (now - parsed).days
    if age_days <= 3:
        return 5
    if age_days <= 14:
        return 2
    return 0
