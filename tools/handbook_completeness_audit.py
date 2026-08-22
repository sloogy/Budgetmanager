#!/usr/bin/env python3
"""Prüft die Benutzerhilfe gegen das implementierte Funktionsinventar.

Der Audit ist absichtlich Qt-frei und kann in CI sowie auf einem nackten
Python-System laufen. Er prüft nicht nur das Vorhandensein von Dateien, sondern
auch zentrale Funktionsgrenzen und bekannte frühere Widersprüche.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_info import APP_VERSION


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    details: str


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def run_audit() -> list[Check]:
    from views.help_content import HELP_TOPICS, help_topic_body, help_topic_title

    checks: list[Check] = []

    expected_topics = {
        "einstieg",
        "kategorien",
        "draganddrop",
        "budget",
        "soft-zero-budget",
        "cockpit",
        "monatsabschluss",
        "buchungen",
        "fixkosten",
        "wiederkehrend",
        "uebersicht",
        "sparziele",
        "favoriten",
        "tags",
        "undoredo",
        "backup",
        "datenbank",
        "konten",
        "update",
        "datenformat",
        "mindmap",
        "lernmodus",
        "pot-rueckstellung",
        "jahreswechsel",
        "suche-filter",
        "export-druck",
        "einstellungen-design",
        "tastenkurzel",
        "datenverwaltung",
        "diagnose",
        "wiki-zusammenhaenge",
    }
    ids = {str(t.get("id")) for t in HELP_TOPICS}
    missing = sorted(expected_topics - ids)
    checks.append(
        Check(
            "In-App-Themeninventar",
            not missing,
            f"{len(ids)} Themen; fehlend: {', '.join(missing) if missing else 'keine'}",
        )
    )

    language_errors: list[str] = []
    for topic in HELP_TOPICS:
        for lang in ("de", "en", "fr"):
            title = help_topic_title(topic, lang).strip()
            body = help_topic_body(topic, lang).strip()
            if len(title) < 2 or len(body) < 180:
                language_errors.append(
                    f"{topic.get('id')}/{lang} title={len(title)} body={len(body)}"
                )
    checks.append(
        Check(
            "Dreisprachige In-App-Hilfe",
            not language_errors,
            (
                "alle Themen ausreichend befüllt"
                if not language_errors
                else "; ".join(language_errors[:12])
            ),
        )
    )

    source_anchors = {
        "Tracking-Lernmodus": (
            "settings_dialog.py",
            ["cb_tracking_budget_learning", "tracking_learning_proposal_months"],
        ),
        "Soft-0-Budget": (
            "settings_dialog.py",
            ["cb_budget_zero_balance_rule", 'start_topic_id="soft-zero-budget"'],
        ),
        "POT/Rückstellung": (
            "model/pot_reserve_model.py",
            ["class PotReserveModel", "rest: float"],
        ),
        "13. Monatslohn": (
            "views/special_income_dialog.py",
            ["class ThirteenthSalaryDialog", "payout_month"],
        ),
        "Jahr kopieren": (
            "views/copy_year_dialog.py",
            ["class CopyYearDialog", "review_overrides"],
        ),
        "Globale Suche": (
            "views/global_search_dialog.py",
            ["class GlobalSearchDialog", "search_text=query"],
        ),
        "CSV/TXT/XLSX/PDF-Export": (
            "views/export_dialog.py",
            ["radio_csv", "radio_txt", "radio_xlsx", "radio_pdf"],
        ),
        "Monatsabschluss-Vermerk": (
            "model/month_close_model.py",
            ["def mark_closed", "system_flags"],
        ),
        "Diagnosebericht": (
            "model/diagnostics.py",
            ["create_diagnostic_report_zip", "sanitized_settings"],
        ),
        "Datenordner-Umzug": (
            "model/data_location.py",
            ["migrate_data_dir", "make_backup"],
        ),
    }
    anchor_failures: list[str] = []
    for feature, (rel, anchors) in source_anchors.items():
        content = _text(rel)
        absent = [a for a in anchors if a not in content]
        if absent:
            anchor_failures.append(f"{feature}: {rel} fehlt {absent}")
    checks.append(
        Check(
            "Funktionsinventar im Quellcode",
            not anchor_failures,
            (
                "alle dokumentierten Kernfunktionen im Code verankert"
                if not anchor_failures
                else "; ".join(anchor_failures)
            ),
        )
    )

    guides = {lang: _text(f"docs/USER_GUIDE.{lang}.md") for lang in ("de", "en", "fr")}
    guide_terms = {
        "de": [
            "Tracking-Lernmodus",
            "POT/Rückstellung",
            "13. Monatslohn",
            "Soft-0-Budget",
            "Monatsabschluss",
            "CSV",
            "XLSX",
            "PDF",
            "GNOME",
            "Fehlerdiagnose",
        ],
        "en": [
            "Tracking learning mode",
            "Pot/Reserve",
            "13th salary",
            "Soft Zero Budget",
            "Month-end close",
            "CSV",
            "XLSX",
            "PDF",
            "GNOME",
            "diagnostics",
        ],
        "fr": [
            "mode apprentissage",
            "POT/Provision",
            "13e salaire",
            "Budget zéro souple",
            "Clôture du mois",
            "CSV",
            "XLSX",
            "PDF",
            "GNOME",
            "diagnostic",
        ],
    }
    missing_terms: list[str] = []
    for lang, terms in guide_terms.items():
        if APP_VERSION not in guides[lang]:
            missing_terms.append(f"{lang}: Version {APP_VERSION}")
        low = guides[lang].lower()
        for term in terms:
            if term.lower() not in low:
                missing_terms.append(f"{lang}: {term}")
    checks.append(
        Check(
            "Benutzerhandbücher DE/EN/FR",
            not missing_terms,
            (
                "Funktionsumfang und Grenzen vollständig"
                if not missing_terms
                else "fehlend: " + ", ".join(missing_terms)
            ),
        )
    )

    active_docs = "\n".join(
        [
            guides["de"],
            _text("docs/help/README.md"),
            _text("views/help_content_additions.py"),
        ]
    )
    forbidden_claims = {
        "Monatsabschluss friert einen Monat": "friert einen Monat",
        "Monat gezielt wieder öffnen": "lässt sich gezielt wieder öffnen",
        "Datenbankverwaltung im Extras-Menü": "Extras → Datenbankverwaltung",
    }
    contradictions = [
        name for name, phrase in forbidden_claims.items() if phrase in active_docs
    ]
    checks.append(
        Check(
            "Widerspruchsfreiheit",
            not contradictions,
            (
                "bekannte Falschaussagen entfernt"
                if not contradictions
                else "gefunden: " + ", ".join(contradictions)
            ),
        )
    )

    export_src = _text("views/export_dialog.py")
    export_topic = next(t for t in HELP_TOPICS if t["id"] == "export-druck")
    export_de = help_topic_body(export_topic, "de")
    export_ok = (
        "radio_csv" in export_src
        and "radio_txt" in export_src
        and "radio_xlsx" in export_src
        and "radio_pdf" in export_src
        and "PDF" in export_de
        and "XLSX" in export_de
        and ".bmr" in export_de
    )
    checks.append(
        Check(
            "Exportgrenzen korrekt",
            export_ok,
            "CSV/TXT/XLSX/PDF vorhanden und klar von .bmr-Backups getrennt",
        )
    )

    month_topic = next(t for t in HELP_TOPICS if t["id"] == "monatsabschluss")
    month_de = help_topic_body(month_topic, "de")
    month_ok = (
        "Vermerk" in month_de
        and "friert den Monat nicht ein" in month_de
        and "def mark_closed" in _text("model/month_close_model.py")
    )
    checks.append(
        Check(
            "Monatsabschluss korrekt beschrieben",
            month_ok,
            "Cockpit-Vermerk statt fachlicher Sperre",
        )
    )

    html = _text("docs/help/index.html")
    html_terms = [
        f"BudgetManager Hilfe {APP_VERSION}",
        "Vereinheitlichte Bedienung",
        "Tracking-Lernmodus",
        "Export, PDF und Drucken",
        "Fehlerdiagnose",
        "<table>",
        "Wiki-Audit und grafische Zusammenhänge",
        "wiki-audit.html",
    ]
    html_missing = [term for term in html_terms if term not in html]
    checks.append(
        Check(
            "Statische HTML-Hilfe",
            not html_missing,
            (
                "synchron und direkt im Browser lesbar"
                if not html_missing
                else "fehlend: " + ", ".join(html_missing)
            ),
        )
    )

    mindmap_errors: list[str] = []
    for lang in ("de", "en", "fr"):
        html_path = ROOT / "docs/help" / f"mindmap.{lang}.html"
        mmd_path = ROOT / "docs/help" / f"mindmap.{lang}.mmd"
        if not html_path.exists() or not mmd_path.exists():
            mindmap_errors.append(lang)
            continue
        combined = html_path.read_text(encoding="utf-8") + mmd_path.read_text(
            encoding="utf-8"
        )
        if "csv" not in combined.lower() or "pot" not in combined.lower():
            mindmap_errors.append(f"{lang}: Inhalt")
    checks.append(
        Check(
            "Mindmaps DE/EN/FR",
            not mindmap_errors,
            (
                "Kernworkflow inklusive POT und Exportgrenzen"
                if not mindmap_errors
                else "Fehler: " + ", ".join(mindmap_errors)
            ),
        )
    )

    graphic_paths = [
        ROOT / "docs/help/wiki-audit.html",
        ROOT / "docs/help/assets/wiki_audit_overview.png",
        ROOT / "docs/help/assets/dataflow_decision_logic.png",
        ROOT / "docs/help/assets/wiki_audit_dashboard.png",
    ]
    missing_graphics = [
        str(p.relative_to(ROOT))
        for p in graphic_paths
        if not p.is_file() or p.stat().st_size < 1000
    ]
    main_window_src = _text("views/main_window.py")
    linux_help_ok = (
        "f\"?  {tr('menu.help')}\"" in main_window_src
        and "self.sidebar_help_button = add_utility" in main_window_src
        and "self._show_handbook" in main_window_src
        and "docs/help/wiki-audit.html" in main_window_src
    )
    checks.append(
        Check(
            "Wiki-Grafiken und Linux-Hilfe",
            not missing_graphics and linux_help_ok,
            (
                "Offline-Grafiken vorhanden; ? Hilfe ist emoji-unabhängig"
                if not missing_graphics and linux_help_ok
                else f"fehlende Grafiken: {missing_graphics}; Linux-Hilfe: {linux_help_ok}"
            ),
        )
    )

    return checks


def report_markdown(checks: list[Check]) -> str:
    passed = sum(c.passed for c in checks)
    lines = [
        f"# Handbuch-Vollständigkeitsaudit v{APP_VERSION}",
        "",
        "## Ergebnis",
        "",
        f"**{passed}/{len(checks)} Prüfbereiche bestanden.**",
        "",
        "| Status | Prüfbereich | Ergebnis |",
        "|---|---|---|",
    ]
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        details = check.details.replace("|", "\\|")
        lines.append(f"| {status} | {check.name} | {details} |")
    lines.extend(
        [
            "",
            "## Wesentliche Korrekturen",
            "",
            "- Monatsabschluss: Erinnerungs-Vermerk statt Monatssperre dokumentiert.",
            "- Datenbankverwaltung: aktueller Pfad über Konto bzw. Einstellungen dokumentiert.",
            "- Export: CSV/TXT/XLSX/PDF vollständig dokumentiert und klar von `.bmr`-Backups abgegrenzt.",
            "- In-App-Hilfe um fehlende Kernbereiche ergänzt und dreisprachig synchronisiert.",
            "- Statische HTML-Hilfe und Mindmaps neu aus den aktuellen Inhalten aufgebaut.",
            "",
            "## Berichtsfunktionen",
            "",
            "Die Version bietet strukturierte CSV-, TXT- und XLSX-Exporte sowie einen drucktauglichen A4-PDF-Bericht. Eine interaktive Druckvorschau bleibt bewusst ausserhalb des Exportdialogs.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    checks = run_audit()
    for check in checks:
        print(f"{'PASS' if check.passed else 'FAIL'}: {check.name} — {check.details}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_markdown(checks), encoding="utf-8")
    return 0 if all(c.passed for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
