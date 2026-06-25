#!/usr/bin/env python3
"""BudgetManager Release-Logik-Audit: 100 schnelle, deterministische Loops.

Prüft keine echten Frozen-Binaries. Dafür werden die kritischen Release-Flächen
statisch und mit headless Geschäftslogik geprüft:
- DE/EN/FR-Hilfe und Übersetzungs-Parität
- Forecast-Denkfehler-Szenarien
- Hardcoded/visible UI-Regressionsmuster
- GitHub-Release-Plattform (Windows, Linux, Installer, Portable-ZIP, latest.json)
- Updater-Pfade für Portable, direkte Binary und Windows-Installer
- Diagramm-Logik und Erklärung
- DAU-/Erststart- und Daten-Sicherheitsregeln, soweit headless prüfbar
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_suggestion_engine import BudgetSuggestionEngine  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS  # noqa: E402

REQUIRED_LANGS = ("de", "en", "fr")


def _flat(obj: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in obj.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flat(value, full))
        else:
            out[full] = str(value)
    return out


def _conn() -> sqlite3.Connection:
    """Sehr kleine In-Memory-DB für Forecast-Logiktests.

    Die Forecast-Engine braucht hier nur categories/budget/tracking. Das ist
    bewusst schneller als migrate_all(), damit 100 Loops deterministisch und
    kurz laufen. Die vollständigen Migrationen prüft die reguläre Pytest-Suite.
    """
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE categories (typ TEXT, name TEXT, is_fix INTEGER, is_recurring INTEGER, recurring_day INTEGER)")
    c.execute("CREATE TABLE budget (year INTEGER, month INTEGER, typ TEXT, category TEXT, amount REAL)")
    c.execute("CREATE TABLE tracking (date TEXT, typ TEXT, category TEXT, amount REAL, details TEXT)")
    return c


def _add_category(conn: sqlite3.Connection, name: str, *, typ: str = TYP_EXPENSES, is_fix=False, is_recurring=False) -> None:
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) VALUES(?,?,?,?,1)",
        (typ, name, 1 if is_fix else 0, 1 if is_recurring else 0),
    )


def _set_budget(conn: sqlite3.Connection, name: str, months: Iterable[tuple[int, int]], amount: float, *, typ: str = TYP_EXPENSES) -> None:
    for y, m in months:
        conn.execute(
            "INSERT OR REPLACE INTO budget(year, month, typ, category, amount) VALUES(?,?,?,?,?)",
            (y, m, typ, name, amount),
        )


def _book(conn: sqlite3.Connection, name: str, months: Iterable[tuple[int, int]], amount: float, *, typ: str = TYP_EXPENSES) -> None:
    if amount == 0:
        return
    for y, m in months:
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
            (f"{y:04d}-{m:02d}-15", typ, name, amount, "audit"),
        )


def check_i18n_and_guides() -> None:
    flats = {
        lang: _flat(json.loads((ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")))
        for lang in REQUIRED_LANGS
    }
    base = set(flats["de"])
    for lang in ("en", "fr"):
        missing = base - set(flats[lang])
        assert not missing, f"{lang}.json missing keys: {sorted(missing)[:10]}"

    spec = importlib.util.spec_from_file_location("budgetmanager_help_content", ROOT / "views" / "help_content.py")
    assert spec and spec.loader, "help_content.py kann nicht geladen werden"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    topics = module.HELP_TOPICS
    assert len(topics) >= 15
    for topic in topics:
        for field in ("title", "body"):
            for lang in REQUIRED_LANGS:
                assert topic[field].get(lang, "").strip(), f"help topic {topic.get('id')} missing {field}.{lang}"

    required_guide_terms = {
        "de": ["Forecast", "Diagramme erklärt", "Updates", "Fixkosten"],
        "en": ["Forecast", "Chart guide", "Updates", "Fixed cost"],
        "fr": ["Prévisions", "Explication des graphiques", "Mises à jour", "Charge fixe"],
    }
    for lang, terms in required_guide_terms.items():
        text = (ROOT / "docs" / f"USER_GUIDE.{lang}.md").read_text(encoding="utf-8")
        import app_info
        assert app_info.APP_VERSION in text
        for term in terms:
            assert term in text, f"guide {lang} missing term {term}"


def check_forecast_logic() -> None:
    # Fixkosten: 0-Monate dürfen nicht senken.
    conn = _conn()
    _add_category(conn, "Versicherung", is_fix=True, is_recurring=True)
    _set_budget(conn, "Versicherung", [(2026, m) for m in range(1, 8)], 200.0)
    _book(conn, "Versicherung", [(2026, 1)], 250.0)
    assert BudgetSuggestionEngine(conn).compute_category_suggestion(TYP_EXPENSES, "Versicherung", 2026, 7) is None
    conn.close()

    # Wiederkehrend ohne fix: ebenfalls geschützt.
    conn = _conn()
    _add_category(conn, "Jahresabo", is_recurring=True)
    _set_budget(conn, "Jahresabo", [(2026, m) for m in range(1, 8)], 120.0)
    _book(conn, "Jahresabo", [(2026, 1)], 120.0)
    assert BudgetSuggestionEngine(conn).compute_category_suggestion(TYP_EXPENSES, "Jahresabo", 2026, 7) is None
    conn.close()

    # Inkrementelle Fixkosten: aktive Monate über Budget dürfen nicht erhöhen,
    # solange das Gesamtbudget im Fenster ausreicht.
    conn = _conn()
    _add_category(conn, "Versicherung", is_fix=True, is_recurring=True)
    _set_budget(conn, "Versicherung", [(2026, m) for m in range(1, 8)], 200.0)
    _book(conn, "Versicherung", [(2026, m) for m in (1, 2, 3)], 250.0)
    assert BudgetSuggestionEngine(conn).compute_category_suggestion(TYP_EXPENSES, "Versicherung", 2026, 7) is None
    conn.close()

    # Wiederholte echte Überschreitung bei Fixkosten darf erhöhen.
    conn = _conn()
    _add_category(conn, "Strom", is_fix=True, is_recurring=True)
    _set_budget(conn, "Strom", [(2026, m) for m in range(1, 8)], 100.0)
    _book(conn, "Strom", [(2026, m) for m in (1, 2, 3, 4, 5, 6)], 160.0)
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(TYP_EXPENSES, "Strom", 2026, 7)
    assert res is not None and res.suggested_budget > 100 and res.direction == "deficit"
    conn.close()

    # Flexible Kategorie: wiederholtes Muster inkl. 0 darf lernen.
    conn = _conn()
    _add_category(conn, "Hobby")
    _set_budget(conn, "Hobby", [(2026, m) for m in range(1, 8)], 40.0)
    for m, amount in [(1, 20), (2, 30), (3, 0), (4, 20), (5, 30), (6, 0)]:
        _book(conn, "Hobby", [(2026, m)], amount)
    res = BudgetSuggestionEngine(conn).compute_category_suggestion(TYP_EXPENSES, "Hobby", 2026, 7)
    assert res is not None and res.suggested_budget < 40.0
    conn.close()

    # Gegensätzliche Ausreißer dürfen keinen Vorschlag erzeugen.
    conn = _conn()
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", [(2026, m) for m in (1, 2, 3)], 400.0)
    _book(conn, "Nahrungsmittel", [(2026, 1)], 450.0)
    _book(conn, "Nahrungsmittel", [(2026, 2)], 350.0)
    assert BudgetSuggestionEngine(conn).compute_category_suggestion(TYP_EXPENSES, "Nahrungsmittel", 2026, 3, months_back=2) is None
    conn.close()

    # Nur ein echter Buchungsmonat nach Start darf keine Fantasie-Vorschläge erzeugen.
    conn = _conn()
    _add_category(conn, "Lohn", typ=TYP_INCOME)
    _add_category(conn, "Hochzeit", typ=TYP_SAVINGS)
    _set_budget(conn, "Lohn", [(2026, m) for m in range(1, 7)], 5000.0, typ=TYP_INCOME)
    _set_budget(conn, "Hochzeit", [(2026, 6)], 400.0, typ=TYP_SAVINGS)
    _book(conn, "Lohn", [(2026, 6)], 5000.0, typ=TYP_INCOME)
    _book(conn, "Hochzeit", [(2026, 6)], 10000.0, typ=TYP_SAVINGS)
    eng = BudgetSuggestionEngine(conn)
    assert eng.compute_category_suggestion(TYP_INCOME, "Lohn", 2026, 6, months_back=3) is None
    assert eng.compute_category_suggestion(TYP_SAVINGS, "Hochzeit", 2026, 6, months_back=3) is None
    conn.close()


def check_no_known_hardcoded_ui_regressions() -> None:
    budget_src = (ROOT / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")
    assert 'QTableWidgetItem("TOTAL")' not in budget_src
    assert 'QTableWidgetItem(tr("header.total"))' in budget_src
    assert 'ROLE_ROW_KIND' in budget_src

    for lang, forbidden in {
        "en": ["Monat", "Bereich", "Bearbeiten", "Fixkosten buchen", "Gesamt/Header"],
        "fr": ["Monat", "Bereich", "Bearbeiten", "Fixkosten buchen", "Gesamt/Header"],
    }.items():
        flat = _flat(json.loads((ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")))
        offenders = [(k, v) for k, v in flat.items() for term in forbidden if term in v]
        assert not offenders, f"known German UI terms leaked into {lang}: {offenders[:5]}"

    # Exakte Regressionen, die der Release verhindern soll. Der vollständige
    # i18n-Scanner läuft zusätzlich außerhalb dieses 100-Loop-Skripts.
    for rel in [
        "views/tabs/budget_tab.py",
        "views/update_dialog.py",
        "views/help_content.py",
        "installer/budgetmanager_setup.iss",
    ]:
        assert (ROOT / rel).exists(), f"missing release-critical file: {rel}"


def check_release_platform_and_updater() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    for needle in [
        "windows-latest",
        "ubuntu-latest",
        "pyinstaller BudgetManager.spec --noconfirm",
        "Build Windows installer",
        "BudgetManager_Setup.exe",
        "tools/build_release_assets.py",
        "release_assets/*",
        "Verify updater manifest stays updater-safe",
        "softprops/action-gh-release@v2",
    ]:
        assert needle in workflow, f"workflow missing {needle}"

    builder = (ROOT / "tools" / "build_release_assets.py").read_text(encoding="utf-8")
    for needle in [
        "BudgetManager-v{version}-portable-windows.zip",
        "BudgetManager-v{version}-portable-linux.zip",
        "BudgetManager_Setup_{version}.zip",
        "SHA256SUMS.txt",
        "WINDOWS_DOWNLOAD_HINWEIS.txt",
        "WINDOWS_CANONICAL_EXE",
        "LINUX_CANONICAL_BINARY",
    ]:
        assert needle in builder, f"release asset builder missing {needle}"

    spec = (ROOT / "BudgetManager.spec").read_text(encoding="utf-8")
    for needle in ["locales", "data/default_categories.json", "docs/help", "resources/icons", "views/profiles", "budgetmanager.ico"]:
        assert needle in spec, f"spec missing {needle}"

    latest = json.loads((ROOT / "latest.json.template").read_text(encoding="utf-8"))
    assets = latest["assets"]
    assert assets["windows"]["type"] == "portable-zip"
    assert assets["linux"]["type"] == "portable-zip"
    assert assets["windows_installer"]["type"] == "installer"
    assert assets["windows_installer_zip"]["type"] == "installer-zip"
    assert assets["windows"]["url"].endswith("portable-windows.zip")
    assert assets["linux"]["url"].endswith("portable-linux.zip")
    assert assets["direct_windows_exe"]["type"] == "exe"
    assert assets["direct_linux_binary"]["type"] == "binary"

    common = (ROOT / "updater" / "common.py").read_text(encoding="utf-8")
    check = (ROOT / "updater" / "check_update.py").read_text(encoding="utf-8")
    apply = (ROOT / "updater" / "apply_update.py").read_text(encoding="utf-8")
    dialog = (ROOT / "views" / "update_dialog.py").read_text(encoding="utf-8")
    for needle in ["windows_installer", "direct_windows_exe", "direct_linux_binary", "portable_zip", "preferred_asset_keys"]:
        assert needle in common
    assert 'asset_type == "installer"' in check
    assert "write_check_result" in check
    assert "CREATE_NEW_CONSOLE" in apply
    assert "_apply_via_windows_installer" in apply
    assert "data" in apply and "updates" in apply
    assert 'return [sys.executable, "--check-update"]' in dialog
    assert 'return [sys.executable, "--apply-update"]' in dialog

    iss = (ROOT / "installer" / "budgetmanager_setup.iss").read_text(encoding="utf-8")
    assert 'Name: "french"; MessagesFile: "compiler:Languages\\French.isl"' in iss
    assert 'SaveStringToFile(ExpandConstant(\'{app}\\installation.json\')' in iss
    for lang in REQUIRED_LANGS:
        prefix = {"de": "german", "en": "english", "fr": "french"}[lang]
        for key in ("DataDirTitle", "PrefsTitle", "LanguageLabel", "CurrencyCHF", "PreferredDayNone"):
            assert f"{prefix}.{key}=" in iss


def check_graphs_and_dau_static() -> None:
    overview_test = (ROOT / "tests" / "test_overview_charts.py").read_text(encoding="utf-8")
    assert "test_range_budget_spans_window_months_not_single_month" in overview_test
    assert "test_aggregate_top_bookings_sums_salary_once" in overview_test

    kpi = (ROOT / "views" / "tabs" / "overview_kpi_panel.py").read_text(encoding="utf-8")
    for needle in [
        "overview.subtab.monthly_trend",
        "overview.subtab.balance_trend",
        "overview.subtab.top_bookings",
        "overview.tip.monthly_trend",
        "overview.tip.balance_trend",
        "overview.tip.top_bookings",
    ]:
        assert needle in kpi

    for lang in REQUIRED_LANGS:
        guide = (ROOT / "docs" / f"USER_GUIDE.{lang}.md").read_text(encoding="utf-8")
        assert ("Diagram" in guide) or ("Chart" in guide) or ("graphique" in guide.lower())
        assert "data/" in guide

    assert not (ROOT / "data" / "users.json").exists()
    assert not list((ROOT / "data").glob("*.enc"))


@dataclass
class LoopResult:
    loop: int
    findings: int


def run_loop(loop_no: int) -> LoopResult:
    check_i18n_and_guides()
    check_forecast_logic()
    check_no_known_hardcoded_ui_regressions()
    check_release_platform_and_updater()
    check_graphs_and_dau_static()
    return LoopResult(loop_no, 0)


def main() -> int:
    results: list[LoopResult] = []
    for i in range(1, 101):
        try:
            results.append(run_loop(i))
        except Exception as exc:
            print(f"LOOP {i}: FAIL: {exc}")
            return 1
    print("BudgetManager Release-Logik-Audit")
    print("Loops: 100")
    print("Status: PASS")
    print("Findings: 0")
    for r in results:
        print(f"Loop {r.loop:03d}: findings={r.findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
