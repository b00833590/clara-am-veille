"""One-off catch-up pass (2026-07-30) : repasse toutes les offres déjà
stockées par le RuleBasedClassifier actuel, pour corriger les faux positifs
d'avant le durcissement des mots-clés (M&A/IB, contrôleur financier, team
assistant, communication visuelle... classés A par défaut alors qu'ils
n'ont rien à voir avec l'Asset Management).

Ne touche jamais cover_letter_link/status/application_* — une lettre déjà
générée ou un statut de candidature déjà saisi par Clara restent intacts.
Ne renvoie aucun email ni ne crée aucun brouillon : uniquement une mise à
jour de classification en base, avant que le prochain run régénère les
exports (Excel, Google Sheet) avec les catégories corrigées.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.classification.rule_based_classifier import RuleBasedClassifier  # noqa: E402
from src.models import JobPosting  # noqa: E402
from src.storage.sqlite_repository import SQLiteJobRepository  # noqa: E402

DB_PATH = ROOT / "data" / "offres.db"


def main() -> None:
    repository = SQLiteJobRepository(DB_PATH)
    classifier = RuleBasedClassifier()

    changed = 0
    unchanged = 0
    for row in repository.all_postings():
        posting = JobPosting(company=row["company"], title=row["title"], url=row["url"], description=row["description"] or "")
        result = classifier.classify(posting)

        if (result.category, result.language, result.to_verify) == (row["category"], row["language"], bool(row["to_verify"])):
            unchanged += 1
            continue

        repository.update_classification(row["stable_id"], result.category, result.language, result.to_verify, result.reason)
        changed += 1
        print(f"[{row['company']}] {row['category']}{'(à verif)' if row['to_verify'] else ''} -> {result.category}{'(à verif)' if result.to_verify else ''} : {row['title']}")

    print(f"\n{changed} offre(s) reclassée(s), {unchanged} inchangée(s).")


if __name__ == "__main__":
    main()
