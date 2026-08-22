#!/usr/bin/env python3
"""Build dependency-free HTML and Mermaid mind maps in DE/EN/FR."""

from __future__ import annotations

import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HELP_DIR = ROOT / "docs/help"

DATA = {
    "de": {
        "title": "BudgetManager Informations-Laufplan",
        "hint": "Diese lokale HTML-Mindmap ohne externe Abhängigkeiten zeigt Funktionen und empfohlene Wege.",
        "footer": "Deutsch",
        "nodes": [
            (
                "🚀 Erststart",
                [
                    "Sprache/Währung/Zahlenformat",
                    "Konto: Quick, PIN oder Passwort",
                    "Restore-Key extern sichern",
                    "Express-Einrichtung oder Lernmodus",
                ],
            ),
            (
                "🏠 Cockpit / Startseite",
                [
                    "Monatsstatus und nächste Schritte",
                    "offene Fix/Wiederholungen",
                    "POT-Reststände",
                    "Aktive Sparziele",
                    "Favoriten und letzte Buchungen",
                    "Monatsabschluss",
                ],
            ),
            (
                "🗂 Kategorien",
                [
                    "Einnahmen/Ausgaben/Ersparnisse",
                    "Haupt- und Unterkategorien",
                    "Fix, wiederkehrend, Fälligkeit",
                    "Forecast: normal, POT, inkrementell",
                    "Tags und Favoriten",
                ],
            ),
            (
                "📒 Budget",
                [
                    "Monat/alle/Bereich",
                    "Jahr kopieren mit Prüfliste",
                    "13. Monatslohn",
                    "Forecast und Lernmodus",
                    "Soft-0-Budget",
                ],
            ),
            (
                "💳 Tracking",
                [
                    "vollständiger Buchungsdialog",
                    "Speichern und weitere hinzufügen",
                    "Fix/Wiederkehrend buchen",
                    "Filter inkl. Parent/Children",
                    "Tags und Sparziel-Entnahmen",
                ],
            ),
            (
                "📊 Übersicht",
                [
                    "Plan/Ist und KPIs",
                    "Zeitraum- und Kombifilter",
                    "Donut, Ranking, Trends",
                    "Top-Buchungen",
                    "Vorschläge prüfen",
                ],
            ),
            (
                "🎯 Sparziele & POT",
                [
                    "Sparziel: fester Zielbetrag",
                    "POT: erwartete unregelmässige Ausgabe",
                    "Einzahlungen/Entnahmen",
                    "Rest und Überschreitungswarnung",
                ],
            ),
            (
                "🛡 Konto & Daten",
                [
                    "Datenordner umziehen",
                    "Backup/Restore .bmr",
                    "Datenbankverwaltung und Reset",
                    "Restore-Key",
                    "Auto-Backup",
                ],
            ),
            (
                "⚙ Einstellungen",
                [
                    "Verhalten und Lernregeln",
                    "Designprofile und GNOME",
                    "Tastenkürzel",
                    "Sprache nach Neustart",
                ],
            ),
            (
                "🔎 Extras & Hilfe",
                [
                    "Globale Suche",
                    "CSV/TXT/XLSX-Export",
                    "A4-PDF-Bericht",
                    "Updates",
                    "Wissensdatenbank",
                    "Logs und Diagnosebericht",
                ],
            ),
        ],
    },
    "en": {
        "title": "BudgetManager information flow",
        "hint": "This local, dependency-free HTML mind map shows key features and recommended paths.",
        "footer": "English",
        "nodes": [
            (
                "🚀 First start",
                [
                    "language/currency/number format",
                    "Quick, PIN or password account",
                    "store restore key externally",
                    "Express setup or learning mode",
                ],
            ),
            (
                "🏠 Cockpit / home",
                [
                    "month status and next steps",
                    "due fixed/recurring items",
                    "pot balances",
                    "active savings goals",
                    "favorites and recent transactions",
                    "month-end close",
                ],
            ),
            (
                "🗂 Categories",
                [
                    "income/expenses/savings",
                    "parent and child categories",
                    "fixed, recurring, due day",
                    "forecast: normal, pot, incremental",
                    "tags and favorites",
                ],
            ),
            (
                "📒 Budget",
                [
                    "one/all/range months",
                    "copy year review",
                    "13th salary",
                    "forecast and learning",
                    "Soft Zero Budget",
                ],
            ),
            (
                "💳 Tracking",
                [
                    "one full transaction dialog",
                    "save and add another",
                    "book fixed/recurring",
                    "filters incl. parent/children",
                    "tags and goal withdrawals",
                ],
            ),
            (
                "📊 Overview",
                [
                    "planned/actual and KPIs",
                    "combined period filters",
                    "donut, ranking, trends",
                    "top transactions",
                    "review suggestions",
                ],
            ),
            (
                "🎯 Goals & pots",
                [
                    "goal: fixed target",
                    "pot: expected irregular expense",
                    "deposits/withdrawals",
                    "remaining reserve and overrun warning",
                ],
            ),
            (
                "🛡 Account & data",
                [
                    "move data folder",
                    "backup/restore .bmr",
                    "database management/reset",
                    "restore key",
                    "automatic backup",
                ],
            ),
            (
                "⚙ Settings",
                [
                    "workflow and learning rules",
                    "design profiles and GNOME",
                    "keyboard shortcuts",
                    "language after restart",
                ],
            ),
            (
                "🔎 Extras & help",
                [
                    "global search",
                    "CSV/TXT/XLSX export",
                    "A4 PDF report",
                    "updates",
                    "knowledge base",
                    "logs and diagnostics",
                ],
            ),
        ],
    },
    "fr": {
        "title": "Parcours d’information BudgetManager",
        "hint": "Cette mindmap HTML locale et sans dépendance montre les fonctions et parcours conseillés.",
        "footer": "Français",
        "nodes": [
            (
                "🚀 Premier démarrage",
                [
                    "langue/devise/format numérique",
                    "compte Quick, PIN ou mot de passe",
                    "conserver la clé hors du dossier",
                    "configuration express ou apprentissage",
                ],
            ),
            (
                "🏠 Cockpit / accueil",
                [
                    "état du mois et prochaines étapes",
                    "charges fixes/récurrentes dues",
                    "restes des POT",
                    "objectifs d’épargne actifs",
                    "favoris et opérations récentes",
                    "clôture du mois",
                ],
            ),
            (
                "🗂 Catégories",
                [
                    "revenus/dépenses/épargne",
                    "catégories principales/enfants",
                    "fixe, récurrent, échéance",
                    "prévision: normal, POT, incrémentiel",
                    "tags et favoris",
                ],
            ),
            (
                "📒 Budget",
                [
                    "un/tous/plage de mois",
                    "copie annuelle contrôlée",
                    "13e salaire",
                    "prévisions et apprentissage",
                    "budget zéro souple",
                ],
            ),
            (
                "💳 Suivi",
                [
                    "un dialogue complet",
                    "enregistrer et ajouter",
                    "charges fixes/récurrentes",
                    "filtres parent/enfants",
                    "tags et retraits d’objectif",
                ],
            ),
            (
                "📊 Aperçu",
                [
                    "prévu/réel et KPI",
                    "filtres de période combinés",
                    "donut, classement, évolutions",
                    "principales opérations",
                    "valider les suggestions",
                ],
            ),
            (
                "🎯 Objectifs & POT",
                [
                    "objectif: montant cible",
                    "POT: dépense irrégulière attendue",
                    "versements/retraits",
                    "reste et alerte de dépassement",
                ],
            ),
            (
                "🛡 Compte & données",
                [
                    "déplacer le dossier",
                    "sauvegarde/restauration .bmr",
                    "gestion/réinitialisation",
                    "clé de restauration",
                    "sauvegarde automatique",
                ],
            ),
            (
                "⚙ Réglages",
                [
                    "comportement et apprentissage",
                    "profils et GNOME",
                    "raccourcis",
                    "langue après redémarrage",
                ],
            ),
            (
                "🔎 Extras & aide",
                [
                    "recherche globale",
                    "export CSV/TXT/XLSX",
                    "rapport PDF A4",
                    "mises à jour",
                    "base de connaissances",
                    "journaux et diagnostic",
                ],
            ),
        ],
    },
}

CSS = "body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:24px;background:#f7f7f8;color:#202124}h1{margin-bottom:8px}.lang{display:flex;gap:.5rem;flex-wrap:wrap;margin:0 0 1rem}.lang a{background:white;border:1px solid #ddd;border-radius:999px;padding:.35rem .7rem;text-decoration:none;color:#0b7285}.node{background:white;border:1px solid #ddd;border-radius:14px;padding:12px 16px;margin:10px;box-shadow:0 1px 4px #0001}.root{font-size:1.4rem;font-weight:700;background:#e9f5ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.node h2{font-size:1.05rem;margin:.1rem 0 .5rem}.node ul{margin:.2rem 0 .2rem 1.2rem;padding:0}.hint,.footer{color:#666}.footer{margin-top:18px;font-size:.9rem}"


def build_mmd(nodes: list[tuple[str, list[str]]]) -> str:
    lines = ["mindmap", "  root((BudgetManager))"]
    for title, items in nodes:
        clean_title = title.split(" ", 1)[1] if title and ord(title[0]) > 127 else title
        lines.append(f"    {clean_title}")
        lines.extend(f"      {item}" for item in items)
    return "\n".join(lines) + "\n"


def build_html(lang: str, data: dict, version: str) -> str:
    nav = '<nav class="lang"><a href="mindmap.de.html">Deutsch</a><a href="mindmap.en.html">English</a><a href="mindmap.fr.html">Français</a></nav>'
    sections = []
    for title, items in data["nodes"]:
        lis = "".join(f"<li>{escape(item)}</li>" for item in items)
        sections.append(
            f'<section class="node"><h2>{escape(title)}</h2><ul>{lis}</ul></section>'
        )
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(data["title"])}</title><style>{CSS}</style></head><body>'
        f'<h1>🧭 {escape(data["title"])}</h1><p class="hint">{escape(data["hint"])}</p>{nav}'
        f'<div class="node root">BudgetManager</div><div class="grid">{"".join(sections)}</div>'
        f'<p class="footer">{escape(data["footer"])} · BudgetManager {escape(version)}</p></body></html>\n'
    )


def main() -> int:
    from app_info import APP_VERSION

    HELP_DIR.mkdir(parents=True, exist_ok=True)
    for lang, data in DATA.items():
        (HELP_DIR / f"mindmap.{lang}.mmd").write_text(
            build_mmd(data["nodes"]), encoding="utf-8"
        )
        (HELP_DIR / f"mindmap.{lang}.html").write_text(
            build_html(lang, data, APP_VERSION), encoding="utf-8"
        )
    shutil.copy2(HELP_DIR / "mindmap.de.mmd", HELP_DIR / "mindmap.mmd")
    shutil.copy2(HELP_DIR / "mindmap.de.html", HELP_DIR / "mindmap.html")
    print("Built mindmaps: de, en, fr and German fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
