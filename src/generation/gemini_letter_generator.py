import time
from typing import Callable

from pydantic import BaseModel

from src.gemini_retry import RateLimiter, call_with_retry, default_rate_limiter
from src.models import JobPosting

PROMPT_TEMPLATE = """Tu rédiges un brouillon de lettre de motivation pour Clara, étudiante en Master in Management à l'ESCP (après une licence Économie et Ingénierie Financière à Paris-Dauphine), pour une candidature à un stage.

RÈGLE ABSOLUE : n'invente jamais une information sur Clara qui ne figure pas dans son CV ci-dessous. Si un élément usuel d'une lettre de motivation ne peut pas être déterminé avec certitude (nom exact du recruteur, date de début précise de l'offre, un fait spécifique sur l'entreprise dont tu n'es pas sûr — chiffres d'AUM, nom de fonds précis, etc.), NE L'AFFIRME PAS dans la lettre : soit reste général sur ce point, soit place-le dans la liste "uncertain_elements" pour que Clara le vérifie elle-même avant l'envoi.

CV de Clara (seule source d'information autorisée sur son parcours) :
---
{cv}
---

Lettre de référence — À UTILISER UNIQUEMENT COMME MODÈLE DE STRUCTURE, DE TON ET DE NIVEAU DE LANGUE (direct, factuel, sobre, sans formules ronflantes). Ne reproduis JAMAIS son contenu tel quel pour cette nouvelle candidature — seulement sa logique de construction (lien école/parcours → expériences pertinentes en 1-2 paragraphes → pourquoi ce poste précis chez cette entreprise précise, avec 1-2 éléments spécifiques et vérifiables plutôt que des généralités → phrase de qualités → clôture/disponibilité) :
---
{reference_letter}
---

Offre visée :
Entreprise : {company}
Titre du poste : {title}
Description de l'offre : {description}
Langue de rédaction requise (code) : {language} — écris l'intégralité de la lettre dans cette langue.

Sélectionne dans le CV les expériences les plus pertinentes pour ce poste précis (pas forcément toutes), et adapte le paragraphe "pourquoi cette entreprise" à cette entreprise précise plutôt que d'utiliser une formule interchangeable.

Réponds avec le texte complet de la lettre (corps uniquement, formule de politesse et signature "Clara Benhamou" incluses) et la liste des éléments non vérifiables à signaler à Clara.
"""


class LetterDraft(BaseModel):
    letter_text: str
    uncertain_elements: list[str] = []


class GeminiLetterGenerator:
    MODEL = "gemini-3.5-flash"

    def __init__(
        self,
        client,
        cv_text: str,
        reference_letter_text: str,
        rate_limiter: RateLimiter = default_rate_limiter,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._client = client
        self._cv_text = cv_text
        self._reference_letter_text = reference_letter_text
        self._rate_limiter = rate_limiter
        self._sleep_fn = sleep_fn

    @classmethod
    def from_api_key(cls, api_key: str, cv_text: str, reference_letter_text: str) -> "GeminiLetterGenerator":
        from google import genai

        return cls(genai.Client(api_key=api_key), cv_text, reference_letter_text)

    def generate(self, posting: JobPosting) -> LetterDraft:
        prompt = PROMPT_TEMPLATE.format(
            cv=self._cv_text,
            reference_letter=self._reference_letter_text,
            company=posting.company,
            title=posting.title,
            description=posting.description,
            language=posting.language or "fr",
        )

        def call():
            return self._client.interactions.create(
                model=self.MODEL,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": LetterDraft.model_json_schema(),
                },
            )

        response = call_with_retry(call, sleep_fn=self._sleep_fn, rate_limiter=self._rate_limiter)
        return LetterDraft.model_validate_json(response.output_text)
