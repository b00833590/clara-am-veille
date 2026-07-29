TIER_1_PARIS = (
    "paris",
    "ile-de-france",
    "île-de-france",
    "la defense",
    "la défense",
    "neuilly",
    "boulogne",
    "levallois",
    "puteaux",
    "nanterre",
    "suresnes",
    "issy-les-moulineaux",
    "courbevoie",
)

TIER_2_LONDON = ("london", "londres")

TIER_3_OTHER_EUROPE = (
    "frankfurt",
    "francfort",
    "luxembourg",
    "zurich",
    "geneva",
    "genève",
    "switzerland",
    "suisse",
    "milan",
    "milano",
    "italy",
    "italie",
    "madrid",
    "barcelona",
    "spain",
    "espagne",
    "amsterdam",
    "netherlands",
    "pays-bas",
    "dublin",
    "ireland",
    "irlande",
    "brussels",
    "bruxelles",
    "belgium",
    "belgique",
    "munich",
    "germany",
    "allemagne",
    "lisbon",
    "lisboa",
    "portugal",
    "copenhagen",
    "copenhague",
    "denmark",
    "danemark",
    "stockholm",
    "sweden",
    "suède",
    "vienna",
    "vienne",
    "austria",
    "autriche",
)


def location_priority(location: str | None) -> int:
    """Ranking signal only — never used to exclude a genuine AM posting, per
    explicit decision. 1 = Paris/Île-de-France, 2 = London, 3 = other major
    European financial centre, 4 = everywhere else or unknown.
    """
    if not location:
        return 4

    haystack = location.lower()

    if any(keyword in haystack for keyword in TIER_1_PARIS):
        return 1
    if any(keyword in haystack for keyword in TIER_2_LONDON):
        return 2
    if any(keyword in haystack for keyword in TIER_3_OTHER_EUROPE):
        return 3
    return 4
