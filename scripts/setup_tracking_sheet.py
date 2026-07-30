"""One-time visual setup for the Google Sheets tracking dashboard.

Unlike src/tracking/sheets_sync.py (run on every pipeline execution to push
posting data), this script only touches sheet STRUCTURE and FORMATTING —
tabs, colors, column widths, dropdowns, conditional formatting, charts,
filter views. It is meant to be run once (or re-run after a deliberate
redesign), not on every pipeline execution: formatting persists on its own
once applied, independently of the data sync.

Usage:
    .venv/Scripts/python.exe scripts/setup_tracking_sheet.py <spreadsheet_id>
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import SOURCES  # noqa: E402
from src.notifications.gmail_auth import get_sheets_service  # noqa: E402
from src.tracking.sheets_sync import HEADERS, SHEET_NAME  # noqa: E402

DASHBOARD_SHEET = "📊 Dashboard"
COMPANIES_SHEET = "🏢 Entreprises"
LEGEND_SHEET = "⚙️ Légende & paramètres"

STATUS_OPTIONS = [
    "Nouvelle",
    "À postuler",
    "Candidature envoyée",
    "Relance envoyée",
    "Entretien",
    "Offre reçue",
    "Refusée",
    "Abandonnée",
]
INTEREST_OPTIONS = ["Élevé", "Moyen", "Faible"]
FIT_OPTIONS = ["Excellente", "Bonne", "Moyenne", "Faible"]

# 0-based column indices into HEADERS, used throughout for ranges/formulas.
COL = {name: i for i, name in enumerate(HEADERS)}
MAX_ROWS = 2000

# Header column bands — visually separates auto-filled data from Clara's
# decisions and ongoing tracking, per her requirement for "une séparation
# claire entre informations collectées et décisions personnelles."
NAVY = {"red": 0.106, "green": 0.220, "blue": 0.392}
PURPLE = {"red": 0.404, "green": 0.306, "blue": 0.654}
AMBER = {"red": 0.706, "green": 0.373, "blue": 0.024}
WHITE = {"red": 1, "green": 1, "blue": 1}

AUTO_COLS = (COL["ID"], COL["Confiance"] + 1)
DECISION_COLS = (COL["Niveau d'intérêt"], COL["Statut"] + 1)
TRACKING_COLS = (COL["Date limite candidature"], COL["Prochaine action"] + 1)

COLUMN_WIDTHS = {
    "ID": 90,
    "Entreprise": 160,
    "Division / Équipe": 130,
    "Titre du poste": 260,
    "Localisation": 130,
    "Lien": 220,
    "Source": 110,
    "Date de découverte": 110,
    "Score de pertinence": 80,
    "Confiance": 90,
    "Niveau d'intérêt": 110,
    "Adéquation profil": 120,
    "Statut": 150,
    "Date limite candidature": 120,
    "Date de candidature": 120,
    "Prochaine relance": 120,
    "Contact / Recruteur": 140,
    "Email contact": 180,
    "Commentaires": 220,
    "Prochaine action": 180,
}

STATUS_ROW_COLORS = {
    "À postuler": {"red": 1, "green": 0.949, "blue": 0.8},
    "Candidature envoyée": {"red": 0.812, "green": 0.886, "blue": 0.953},
    "Relance envoyée": {"red": 0.816, "green": 0.878, "blue": 0.882},
    "Entretien": {"red": 0.851, "green": 0.918, "blue": 0.827},
    "Offre reçue": {"red": 0.714, "green": 0.843, "blue": 0.659},
    "Refusée": {"red": 0.957, "green": 0.8, "blue": 0.8},
    "Abandonnée": {"red": 0.851, "green": 0.851, "blue": 0.851},
}

# Statuses that mean "this posting's clock has stopped" — the overdue
# follow-up alert must not fire once Clara has already closed the loop.
TERMINAL_STATUSES = ["Offre reçue", "Refusée", "Abandonnée"]


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: setup_tracking_sheet.py <spreadsheet_id>")
        sys.exit(1)
    spreadsheet_id = sys.argv[1]

    service = get_sheets_service(ROOT / "client_secret.json", ROOT / "token.json")

    sheet_ids = _ensure_tabs(service, spreadsheet_id)
    print(f"Onglets prêts : {sheet_ids}")

    _format_offres_tab(service, spreadsheet_id, sheet_ids[SHEET_NAME])
    print("Mise en forme de l'onglet Offres appliquée.")

    _build_dashboard_tab(service, spreadsheet_id, sheet_ids[DASHBOARD_SHEET])
    print("Dashboard construit.")

    _build_companies_tab(service, spreadsheet_id, sheet_ids[COMPANIES_SHEET])
    print("Onglet Entreprises construit.")

    _build_legend_tab(service, spreadsheet_id, sheet_ids[LEGEND_SHEET])
    print("Onglet Légende construit.")

    _create_filter_views(service, spreadsheet_id, sheet_ids[SHEET_NAME])
    print("Vues filtrées créées.")

    print("Terminé.")


def _ensure_tabs(service, spreadsheet_id: str) -> dict[str, int]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    requests = []
    wanted_order = [SHEET_NAME, DASHBOARD_SHEET, COMPANIES_SHEET, LEGEND_SHEET]

    # The very first tab in a brand-new spreadsheet is "Suivi candidatures"
    # (the Phase 4 name) — rename it in place rather than creating a
    # duplicate, so its sheetId (and any link Clara may have opened) survives.
    if SHEET_NAME not in existing and "Suivi candidatures" in existing:
        old_id = existing.pop("Suivi candidatures")
        requests.append({"updateSheetProperties": {
            "properties": {"sheetId": old_id, "title": SHEET_NAME},
            "fields": "title",
        }})
        existing[SHEET_NAME] = old_id

    for title in wanted_order:
        if title not in existing:
            requests.append({"addSheet": {"properties": {"title": title}}})

    if not requests:
        return existing

    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
    for reply in response.get("replies", []):
        if "addSheet" in reply:
            props = reply["addSheet"]["properties"]
            existing[props["title"]] = props["sheetId"]

    return existing


def _format_offres_tab(service, spreadsheet_id: str, sheet_id: int) -> None:
    _clear_existing_conditional_formats(service, spreadsheet_id, sheet_id)

    requests = [
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }},
        _header_band_request(sheet_id, *AUTO_COLS, NAVY),
        _header_band_request(sheet_id, *DECISION_COLS, PURPLE),
        _header_band_request(sheet_id, *TRACKING_COLS, AMBER),
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 34},
            "fields": "pixelSize",
        }},
    ]
    for name, width in COLUMN_WIDTHS.items():
        idx = COL[name]
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": idx, "endIndex": idx + 1},
            "properties": {"pixelSize": width},
            "fields": "pixelSize",
        }})

    requests.append(_dropdown_request(sheet_id, COL["Statut"], STATUS_OPTIONS))
    requests.append(_dropdown_request(sheet_id, COL["Niveau d'intérêt"], INTEREST_OPTIONS))
    requests.append(_dropdown_request(sheet_id, COL["Adéquation profil"], FIT_OPTIONS))

    requests.extend(_conditional_formatting_requests(sheet_id))

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _clear_existing_conditional_formats(service, spreadsheet_id: str, sheet_id: int) -> None:
    # Makes re-running this script idempotent instead of piling up duplicate
    # rules each time — this script is expected to be re-run after design
    # tweaks, not just once ever.
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId),conditionalFormats)").execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        count = len(sheet.get("conditionalFormats", []))
        if count:
            requests = [{"deleteConditionalFormatRule": {"sheetId": sheet_id, "index": i}} for i in range(count - 1, -1, -1)]
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _header_band_request(sheet_id: int, start_col: int, end_col: int, color: dict) -> dict:
    return {"repeatCell": {
        "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": start_col, "endColumnIndex": end_col},
        "cell": {"userEnteredFormat": {
            "backgroundColor": color,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
    }}


def _dropdown_request(sheet_id: int, col_index: int, options: list[str]) -> dict:
    return {"setDataValidation": {
        "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": MAX_ROWS, "startColumnIndex": col_index, "endColumnIndex": col_index + 1},
        "rule": {
            "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": opt} for opt in options]},
            "strict": True,
            "showCustomUi": True,
        },
    }}


def _conditional_formatting_requests(sheet_id: int) -> list[dict]:
    full_range = {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": MAX_ROWS, "startColumnIndex": 0, "endColumnIndex": len(HEADERS)}
    status_col_letter = _col_letter(COL["Statut"])
    requests = []

    # One rule per status value — colors the whole row so a status is
    # recognizable at a glance while scrolling, not just from the Statut cell.
    for status, color in STATUS_ROW_COLORS.items():
        requests.append({"addConditionalFormatRule": {
            "rule": {
                "ranges": [full_range],
                "booleanRule": {
                    "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f'=${status_col_letter}2="{status}"'}]},
                    "format": {"backgroundColor": color},
                },
            },
            "index": 0,
        }})

    # Overdue follow-up alert: Prochaine relance is in the past and the
    # posting isn't already closed out (accepted/rejected/abandoned) —
    # those postings don't need a relance anymore regardless of the date.
    #
    # Deliberately built from multiplied boolean terms rather than
    # AND(...)/OR(...)/NOT(...) calls: the Sheets API's conditional-format
    # formula validator rejects otherwise-valid formulas that combine one of
    # those functions with 2+ arguments (confirmed by bisection — e.g. even
    # `=AND(1,1,1)` or `=OR(TRUE,FALSE)` alone are rejected, while the
    # arithmetic equivalent below is accepted). Also avoids `TODAY()` and
    # `<>""` sitting directly against a following "," or ")", which trips
    # the same validator — hence `TODAY()+0` and `LEN(...)>0`.
    followup_col_letter = _col_letter(COL["Prochaine relance"])
    terminal_terms = "*".join(f'(${status_col_letter}2<>"{s}")' for s in TERMINAL_STATUSES)
    formula = f'=(LEN(${followup_col_letter}2)>0)*(${followup_col_letter}2<TODAY()+0)*{terminal_terms}'
    requests.append({"addConditionalFormatRule": {
        "rule": {
            "ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": MAX_ROWS, "startColumnIndex": COL["Prochaine relance"], "endColumnIndex": COL["Prochaine relance"] + 1}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]},
                "format": {"backgroundColor": {"red": 0.918, "green": 0.263, "blue": 0.208}, "textFormat": {"foregroundColor": WHITE, "bold": True}},
            },
        },
        "index": 0,
    }})

    return requests


# This spreadsheet's locale is fr_FR (see Fichier > Paramètres), which
# changes what a *cell formula* (as opposed to a conditional-format/filter
# CUSTOM_FORMULA, an entirely different, English-only, comma-separated
# parser — confirmed empirically) actually accepts: the argument separator
# is ";" not ",", and a handful of functions only exist under their French
# name (COUNTIF -> NB.SI, COUNTIFS -> NB.SI.ENS, MATCH -> EQUIV). Others
# (COUNTA, INDEX, MAX, TODAY) keep their English name, just the ";".
def _countif(range_expr: str, criteria: str) -> str:
    return f"NB.SI({range_expr};{criteria})"


def _countifs(*range_criteria_pairs: str) -> str:
    return f"NB.SI.ENS({';'.join(range_criteria_pairs)})"


def _index(range_expr: str, position: str) -> str:
    return f"INDEX({range_expr};{position})"


def _match(needle: str, range_expr: str, match_type: str = "0") -> str:
    return f"EQUIV({needle};{range_expr};{match_type})"


def _col_letter(index: int) -> str:
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _build_dashboard_tab(service, spreadsheet_id: str, sheet_id: int) -> None:
    offres_ref = f"'{SHEET_NAME}'!"
    id_col = _col_letter(COL["ID"])
    status_col = _col_letter(COL["Statut"])
    followup_col = _col_letter(COL["Prochaine relance"])
    company_col = _col_letter(COL["Entreprise"])

    id_range = f"{offres_ref}{id_col}2:{id_col}{MAX_ROWS}"
    status_range = f"{offres_ref}{status_col}2:{status_col}{MAX_ROWS}"
    followup_range = f"{offres_ref}{followup_col}2:{followup_col}{MAX_ROWS}"
    company_range = f"{offres_ref}{company_col}2:{company_col}{MAX_ROWS}"

    # A blank Statut criteria on its own would match every never-populated
    # row out to MAX_ROWS, not just real postings with no status yet — pair
    # it with "ID is non-blank" so only actual rows count.
    def _blank_status_count() -> str:
        return _countifs(status_range, '""', id_range, '"<>"')

    values = [
        ["Tableau de bord — Recherche de stage Asset Management", ""],
        ["", ""],
        ["Indicateur", "Valeur"],
        ["Offres pertinentes détectées", f'=COUNTA({id_range})'],
        ["Candidatures envoyées", "=" + "+".join([
            _countif(status_range, '"Candidature envoyée"'),
            _countif(status_range, '"Relance envoyée"'),
            _countif(status_range, '"Entretien"'),
            _countif(status_range, '"Offre reçue"'),
        ])],
        ["Entretiens obtenus", "=" + _countif(status_range, '"Entretien"') + "+" + _countif(status_range, '"Offre reçue"')],
        ["Offres reçues", "=" + _countif(status_range, '"Offre reçue"')],
        ["Encore à traiter (pas de statut / à postuler)", "=" + _blank_status_count() + "+" + _countif(status_range, '"À postuler"')],
        ["Relances en retard", "=" + _countifs(followup_range, '"<"&TODAY()', followup_range, '"<>"')],
        ["Entreprise la plus représentée", "=" + _index(company_range, _match(f"MAX({_countif(company_range, company_range)})", _countif(company_range, company_range)))],
        ["", ""],
        ["Répartition par statut", ""],
    ]
    # Status breakdown table for the pie chart source.
    status_start_row = len(values) + 1  # 1-based row where the breakdown table starts
    for status in STATUS_OPTIONS:
        values.append([status, "=" + _countif(status_range, f'"{status}"')])
    values.append(["(vide / non renseigné)", "=" + _blank_status_count()])
    status_end_row = len(values) + 1

    _clear_existing_charts(service, spreadsheet_id, sheet_id)

    requests = [{
        "updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
            "rows": [{"values": [{"userEnteredValue": _cell_value(v)} for v in row]} for row in values],
            "fields": "userEnteredValue",
        }
    }, {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14}}},
            "fields": "userEnteredFormat.textFormat",
        }
    }, {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": WHITE}, "backgroundColor": NAVY}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 320},
            "fields": "pixelSize",
        }
    }, {
        "addChart": {
            "chart": {
                "spec": {
                    "title": "Répartition des candidatures par statut",
                    "pieChart": {
                        "legendPosition": "RIGHT_LEGEND",
                        "domain": {"sourceRange": {"sources": [{"sheetId": sheet_id, "startRowIndex": status_start_row - 1, "endRowIndex": status_end_row - 1, "startColumnIndex": 0, "endColumnIndex": 1}]}},
                        "series": {"sourceRange": {"sources": [{"sheetId": sheet_id, "startRowIndex": status_start_row - 1, "endRowIndex": status_end_row - 1, "startColumnIndex": 1, "endColumnIndex": 2}]}},
                    },
                },
                "position": {"overlayPosition": {"anchorCell": {"sheetId": sheet_id, "rowIndex": 2, "columnIndex": 3}, "widthPixels": 480, "heightPixels": 320}},
            }
        }
    }]

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _build_companies_tab(service, spreadsheet_id: str, sheet_id: int) -> None:
    _clear_existing_charts(service, spreadsheet_id, sheet_id)

    offres_ref = f"'{SHEET_NAME}'!"
    company_col = _col_letter(COL["Entreprise"])
    status_col = _col_letter(COL["Statut"])

    company_range = f"{offres_ref}{company_col}2:{company_col}{MAX_ROWS}"
    status_range = f"{offres_ref}{status_col}2:{status_col}{MAX_ROWS}"

    header = ["Entreprise", "Offres pertinentes trouvées", "Candidatures envoyées"]
    rows = [header]
    for source in SOURCES:
        company = source.company
        rows.append([
            company,
            "=" + _countif(company_range, f'"{company}"'),
            "=" + _countifs(company_range, f'"{company}"', status_range, '"<>"', status_range, '"<>Nouvelle"'),
        ])

    requests = [{
        "updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
            "rows": [{"values": [{"userEnteredValue": _cell_value(v)} for v in row]} for row in rows],
            "fields": "userEnteredValue",
        }
    }, {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(header)},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "foregroundColor": WHITE}, "backgroundColor": NAVY}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }
    }, {
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 220},
            "fields": "pixelSize",
        }
    }, {
        "addChart": {
            "chart": {
                "spec": {
                    "title": "Offres pertinentes par entreprise",
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "NO_LEGEND",
                        "domains": [{"domain": {"sourceRange": {"sources": [{"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": len(rows), "startColumnIndex": 0, "endColumnIndex": 1}]}}}],
                        "series": [{"series": {"sourceRange": {"sources": [{"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": len(rows), "startColumnIndex": 1, "endColumnIndex": 2}]}}}],
                    },
                },
                "position": {"overlayPosition": {"anchorCell": {"sheetId": sheet_id, "rowIndex": 1, "columnIndex": 4}, "widthPixels": 600, "heightPixels": 360}},
            }
        }
    }]

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _build_legend_tab(service, spreadsheet_id: str, sheet_id: int) -> None:
    rows = [
        ["Légende & repères", ""],
        ["", ""],
        ["Groupes de colonnes (couleur d'en-tête)", ""],
        ["🔵 Bleu marine — Auto", "Rempli automatiquement par le pipeline. Ne pas modifier à la main : sera écrasé au prochain passage."],
        ["🟣 Violet — Décision rapide", "À remplir par Clara après lecture de l'offre : intérêt, adéquation, statut de candidature."],
        ["🟡 Ambre — Suivi d'action", "Suivi du processus de candidature au fil de l'eau : dates, contact, commentaires, prochaine action."],
        ["", ""],
        ["Couleur de ligne (Statut)", ""],
    ]
    for status, color in STATUS_ROW_COLORS.items():
        rows.append([status, ""])
    rows.append(["Ligne rouge (colonne Prochaine relance)", "La date de relance prévue est dépassée et le dossier n'est pas encore clos (Offre reçue / Refusée / Abandonnée)."])
    rows.append(["", ""])
    rows.append(["Statuts disponibles", ""])
    for status in STATUS_OPTIONS:
        rows.append([status, ""])
    rows.append(["", ""])
    rows.append(["Score de pertinence (0-100)", "Calculé automatiquement (catégorie + priorité géographique + fraîcheur + confiance de classification). Sert à trier, jamais à exclure — voir src/scoring/relevance_scorer.py."])
    rows.append(["Confiance", "\"Confiant\" = mots-clés univoques. \"À vérifier\" = signal ambigu, à relire avant de se fier à la classification."])

    requests = [{
        "updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
            "rows": [{"values": [{"userEnteredValue": _cell_value(v)} for v in row]} for row in rows],
            "fields": "userEnteredValue",
        }
    }, {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True, "fontSize": 14}}},
            "fields": "userEnteredFormat.textFormat",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 320},
            "fields": "pixelSize",
        }
    }, {
        "updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 480},
            "fields": "pixelSize",
        }
    }]
    # Row-color swatches for each status line in the legend, mirroring the
    # conditional formatting applied to the Offres tab.
    for i, (status, color) in enumerate(STATUS_ROW_COLORS.items()):
        row_index = 8 + i  # matches the loop order above (rows list index)
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": 2},
            "cell": {"userEnteredFormat": {"backgroundColor": color}},
            "fields": "userEnteredFormat.backgroundColor",
        }})

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _create_filter_views(service, spreadsheet_id: str, sheet_id: int) -> None:
    _clear_existing_filter_views(service, spreadsheet_id, sheet_id)

    status_col = COL["Statut"]
    followup_col = COL["Prochaine relance"]
    full_range = {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": MAX_ROWS, "startColumnIndex": 0, "endColumnIndex": len(HEADERS)}

    # ONE_OF_LIST isn't a supported ConditionType for filter criteria (only
    # for data validation / conditional formatting) — CUSTOM_FORMULA works
    # for all three instead. Arithmetic (sum/product), not AND(...)/OR(...):
    # see the comment in _conditional_formatting_requests for why the API's
    # formula validator rejects those. Referencing row 2, matching the same
    # top-of-range convention used for conditional formatting formulas.
    status_col_letter = _col_letter(status_col)
    followup_col_letter = _col_letter(followup_col)
    requests = [
        {"addFilterView": {"filter": {
            "title": "À traiter",
            "range": full_range,
            "criteria": {str(status_col): {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f'=(LEN(${status_col_letter}2)=0)+(${status_col_letter}2="À postuler")>0'}]}}},
        }}},
        {"addFilterView": {"filter": {
            "title": "Candidatures en cours",
            "range": full_range,
            "criteria": {str(status_col): {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f'=(${status_col_letter}2="Candidature envoyée")+(${status_col_letter}2="Relance envoyée")+(${status_col_letter}2="Entretien")>0'}]}}},
        }}},
        {"addFilterView": {"filter": {
            "title": "Relances cette semaine",
            "range": full_range,
            "criteria": {str(followup_col): {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": f'=(LEN(${followup_col_letter}2)>0)*(${followup_col_letter}2<=TODAY()+7)'}]}}},
        }}},
    ]

    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _clear_existing_charts(service, spreadsheet_id: str, sheet_id: int) -> None:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId),charts)").execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        chart_ids = [c["chartId"] for c in sheet.get("charts", [])]
        if chart_ids:
            requests = [{"deleteEmbeddedObject": {"objectId": cid}} for cid in chart_ids]
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _clear_existing_filter_views(service, spreadsheet_id: str, sheet_id: int) -> None:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId),filterViews)").execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["sheetId"] != sheet_id:
            continue
        filter_ids = [fv["filterViewId"] for fv in sheet.get("filterViews", [])]
        if filter_ids:
            requests = [{"deleteFilterView": {"filterId": fid}} for fid in filter_ids]
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()


def _cell_value(value) -> dict:
    if isinstance(value, str) and value.startswith("="):
        return {"formulaValue": value}
    return {"stringValue": str(value)}


if __name__ == "__main__":
    main()
