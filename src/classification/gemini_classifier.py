import time
from typing import Callable, Literal

from pydantic import BaseModel

from src.gemini_retry import RateLimiter, call_with_retry, default_rate_limiter
from src.models import JobPosting

PROMPT_TEMPLATE = """Tu classes une offre de stage pour Clara, étudiante cherchant un stage en Asset Management (AM) au sens strict.

Catégorie A — "AM prioritaire" : UNIQUEMENT les stages au plus près de la gestion d'actifs, de l'analyse financière, de la recherche investissement ou de la gestion de portefeuille. Exemples de postes qui appartiennent à cette catégorie : Portfolio Analyst Intern, Investment Analyst Intern, Equity Research Intern, Fixed Income Analyst Intern, Multi-Asset Analyst Intern, Fund Analyst Intern, Portfolio Management Intern, Quantitative Research Intern (dans un contexte d'investissement, pas de la data science généraliste), Investment Solutions Intern, Asset Allocation Intern, gérant de portefeuille, analyste macro/stratégiste sur des fonds, product specialist AM, sales/relations investisseurs pour des produits de gestion (gestion privée ou institutionnelle).

Catégorie B — "Finance intéressant, hors AM" : les autres stages FINANCE analytiques et front-office chez cette même entreprise (corporate finance, M&A, marchés de capitaux, recherche actions sell-side...). Ce n'est PAS un fourre-tout pour toute fonction support d'une société financière.

Catégorie N — "Hors sujet" : tout le reste, MÊME si l'offre est publiée par une société de gestion ou une institution financière. Exclus systématiquement en N, quel que soit l'employeur : RSE, ESG/Sustainability (sauf si le rôle est une analyse investissement directement intégrée à la gestion de portefeuille — précise-le dans reason si c'est le cas limite), Marketing, Communication, RH, Juridique, Compliance, Risques non liés à l'investissement, IT, Développement IA, Data Science généraliste, Opérations, Finance d'entreprise, Contrôle de gestion, Audit, Vente, Business Development, Product Management, Support, Transformation, Stratégie interne, etc. Ces offres apparaissent parce qu'un simple mot-clé "stage" les a fait remonter — le fait que l'employeur soit une société de gestion ne rend pas le poste pertinent si la mission elle-même n'est pas de l'investissement.

En cas de doute entre A et B (mais le poste est bien un rôle d'analyse/investissement front-office), classe en A et mets to_verify=true. N'utilise jamais to_verify pour un doute entre finance et N — si la mission n'est pas de l'investissement, classe N directement même si l'employeur est prestigieux en AM.

Pour toute offre classée A, le champ reason doit expliquer précisément pourquoi elle est pertinente pour une candidature en Asset Management et quelles compétences en investissement ou en gestion de portefeuille elle permet de développer (2-3 phrases).

Détecte aussi la langue de l'annonce (code "fr" ou "en").

Entreprise : {company}
Titre du poste : {title}
Description : {description}
"""


class ClassificationResult(BaseModel):
    category: Literal["A", "B", "N"]
    language: str
    to_verify: bool
    reason: str = ""


class GeminiClassifier:
    MODEL = "gemini-3.5-flash"

    def __init__(
        self,
        client,
        rate_limiter: RateLimiter = default_rate_limiter,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._client = client
        self._rate_limiter = rate_limiter
        self._sleep_fn = sleep_fn

    @classmethod
    def from_api_key(cls, api_key: str) -> "GeminiClassifier":
        from google import genai

        return cls(genai.Client(api_key=api_key))

    def classify(self, posting: JobPosting) -> ClassificationResult:
        prompt = PROMPT_TEMPLATE.format(company=posting.company, title=posting.title, description=posting.description)

        def call():
            return self._client.interactions.create(
                model=self.MODEL,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ClassificationResult.model_json_schema(),
                },
            )

        response = call_with_retry(call, sleep_fn=self._sleep_fn, rate_limiter=self._rate_limiter)
        return ClassificationResult.model_validate_json(response.output_text)
