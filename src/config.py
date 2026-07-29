from dataclasses import dataclass

from src.fetchers.axa_im import AxaIMFetcher
from src.fetchers.base import Fetcher
from src.fetchers.blackrock import BlackRockFetcher
from src.fetchers.comgest import ComgestFetcher
from src.fetchers.jpmorgan import JPMorganFetcher
from src.fetchers.goldman_sachs import GoldmanSachsFetcher
from src.fetchers.flatchr import FlatchrFetcher
from src.fetchers.natixis_group import NatixisGroupFetcher
from src.fetchers.natixis_im import NatixisIMFetcher
from src.fetchers.oracle_hcm import OracleHcmFetcher
from src.fetchers.smartrecruiters import SmartRecruitersFetcher
from src.fetchers.talentsoft import TalentsoftFetcher
from src.fetchers.workday import WorkdayFetcher


@dataclass
class SourceConfig:
    company: str
    fetcher: Fetcher | None
    note: str = ""


# État au 2026-07-20 — voir CLAUDE.md "Périmètre" pour le détail de la vérification
# par entreprise. Seules les sources dont l'URL/endpoint a été confirmée avec un
# niveau de confiance suffisant sont câblées ici ; les autres restent `fetcher=None`
# en attendant un connecteur dédié (Phase 1 suite) plutôt que de risquer un
# scraping silencieusement cassé ou incomplet.
SOURCES: list[SourceConfig] = [
    SourceConfig(
        "Sycomore Asset Management",
        SmartRecruitersFetcher(company_identifier="SycomoreAssetManagement", display_name="Sycomore Asset Management"),
    ),
    SourceConfig(
        "Wellington Management",
        WorkdayFetcher(tenant="wellington", wd_host="wellington.wd5.myworkdayjobs.com", site="Campus", display_name="Wellington Management"),
    ),
    SourceConfig(
        "Capital Group",
        WorkdayFetcher(tenant="capgroup", wd_host="capgroup.wd1.myworkdayjobs.com", site="capitalgroupcareers", display_name="Capital Group"),
    ),
    SourceConfig(
        "Amundi",
        TalentsoftFetcher(base_url="https://jobs.amundi.com", display_name="Amundi"),
    ),
    SourceConfig("BNP Paribas", None, note="Protection anti-bot forte confirmée (403 'Access Denied' même en rendu Playwright complet) — pas un simple problème technique de scraping, contourner activement une protection de ce niveau n'est pas souhaitable. À surveiller manuellement en l'état."),
    SourceConfig(
        "Lazard",
        OracleHcmFetcher(host="icbpjb.fa.ocs.oraclecloud.com", site_number="LazardStudentCareers", display_name="Lazard"),
    ),
    SourceConfig("Carmignac", None, note="Aucun ATS — ni sur Welcome to the Jungle ('non inscrite') ni trouvée sur JobTeaser (slug direct en 404, recherche par mot-clé ne fonctionne pas comme attendu — renvoie des pages SEO génériques sans rapport). Piste job board tiers à considérer épuisée pour l'instant ; à surveiller manuellement."),
    SourceConfig(
        "Candriam",
        TalentsoftFetcher(base_url="https://jobs.candriam.com", display_name="Candriam"),
    ),
    SourceConfig(
        "Comgest",
        ComgestFetcher(url="https://www.comgest.com/en/about-us/our-people/careers/job-offers", display_name="Comgest"),
    ),
    SourceConfig("Natixis", NatixisGroupFetcher()),
    SourceConfig("Natixis Investment Managers", NatixisIMFetcher()),
    SourceConfig("Axa Investment Managers", AxaIMFetcher()),
    SourceConfig("JP Morgan Asset Management", JPMorganFetcher()),
    SourceConfig("Goldman Sachs Asset Management", GoldmanSachsFetcher()),
    SourceConfig("BlackRock", BlackRockFetcher()),
    SourceConfig(
        "Fidelity International",
        WorkdayFetcher(tenant="fil", wd_host="fil.wd3.myworkdayjobs.com", site="001", display_name="Fidelity International"),
    ),
    SourceConfig(
        "Pimco",
        WorkdayFetcher(tenant="pimco", wd_host="pimco.wd1.myworkdayjobs.com", site="pimco-careers", display_name="Pimco"),
    ),
    SourceConfig(
        "Edmond de Rothschild",
        OracleHcmFetcher(host="evht.fa.ocs.oraclecloud.eu", site_number="CX_7001", display_name="Edmond de Rothschild", locale="fr"),
    ),
    SourceConfig(
        "Schroders",
        OracleHcmFetcher(host="ekbq.fa.em2.oraclecloud.com", site_number="CX_2", display_name="Schroders"),
    ),
    SourceConfig(
        "Invesco",
        WorkdayFetcher(tenant="invesco", wd_host="invesco.wd1.myworkdayjobs.com", site="IVZ", display_name="Invesco"),
    ),
    SourceConfig(
        "M&G",
        WorkdayFetcher(tenant="mgpru", wd_host="mgpru.wd3.myworkdayjobs.com", site="mandgprudential", display_name="M&G"),
    ),
    SourceConfig(
        "OFI Invest",
        FlatchrFetcher(url="https://ofiinvestassetmanagement.flatchr.io/", display_name="OFI Invest"),
    ),
    SourceConfig("DNCA Finance", None, note="DigitalRecruiters — confirmé cassé de bout en bout : accueil/annonces/API interne (api.digitalrecruiters.com, y compris depuis une session navigateur réelle) en 403/404, et même une page individuelle indexée par Google (/fr/annonce/3467775-...) renvoie désormais 404. Pas un problème de technique de scraping, le site est génuinement en panne côté DNCA. À réessayer périodiquement."),
    SourceConfig("La Financière de l'Échiquier", None, note="Aucun ATS — pas trouvée sur Welcome to the Jungle ni sur JobTeaser avec les slugs/recherches essayés. Piste job board tiers à considérer épuisée pour l'instant ; à surveiller manuellement."),
    SourceConfig("Pictet", None, note="SAP SuccessFactors confirmé (career012.successfactors.eu/career?company=banquepict, 51 offres visibles côté UI le 2026-07-22) mais instance legacy basée sur DWR (Direct Web Remoting, protocole AJAX-RPC Java à état de session) plutôt qu'une API REST/JSON claire comme les autres connecteurs SuccessFactors-like. Une requête GET directe avec le token _s.crb extrait de la session ne renvoie que le squelette de page (0 offre dans la réponse) — la vraie donnée nécessite de rejouer la séquence d'appels DWR (getInitialJobSearchData → updateUserSelectedValues → getPostingCount), plus fragile et plus coûteux que tout connecteur existant. Pas un problème de scraping classique ; à reprendre si l'effort est jugé justifié plutôt qu'à improviser."),
    SourceConfig("Janus Henderson", None, note="SAP SuccessFactors Career Site Builder confirmé (jobs.janushenderson.com, identifiant company=Janus trouvé dans le HTML) — variante plus moderne que Pictet (endpoint REST/JSON réel POST /services/jobs/search/, pas de DWR), mais renvoie systématiquement {\"jobList\":[]} même avec company=Janus dans le payload : un paramètre requis (probablement lié à la session/cookie initiale, ou un champ obligatoire non identifié) manque encore. Investigué le 2026-07-22, pas résolu dans le temps imparti — à reprendre plutôt qu'à deviner un payload au hasard."),
]


def active_sources() -> list[tuple[str, Fetcher]]:
    return [(source.company, source.fetcher) for source in SOURCES if source.fetcher is not None]


def pending_sources() -> list[SourceConfig]:
    return [source for source in SOURCES if source.fetcher is None]
