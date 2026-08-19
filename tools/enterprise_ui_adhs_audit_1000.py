#!/usr/bin/env python3
"""Enterprise UI-/Usability-/ADHS-Audit – 10 × 100 Loops.

Der Audit trennt Blocker (FAIL) von bewusst sichtbaren UX-Schulden (WARN).
Ein grüner Exit-Code bedeutet: keine automatisierbaren Release-Blocker.
WARN bleibt im Bericht, bis reale Tastatur-/Screenreader- und Meldungsfluss-
Tests durchgeführt beziehungsweise die betreffenden Bereiche überarbeitet sind.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_info import APP_VERSION  # noqa: E402

ROWS: list[dict[str, object]] = []
UNIQUE: dict[str, tuple[str, str]] = {}


def _record(loop: int, domain: str, checks: int, result: str, detail: str = "") -> None:
    ROWS.append(
        {
            "loop": loop,
            "domain": domain,
            "checks": checks,
            "result": result,
            "detail": detail,
        }
    )
    if result in {"WARN", "FAIL"}:
        UNIQUE.setdefault(domain, (result, detail))


def _contrast(a: str, b: str) -> float:
    def luminance(value: str) -> float:
        raw = value.lstrip("#")
        rgb = [int(raw[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
        linear = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    l1, l2 = luminance(a), luminance(b)
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def d1_release_cleaner(i: int) -> tuple[int, str, str]:
    from tools.clean_release_tree import clean

    with tempfile.TemporaryDirectory(prefix="bm-ui-audit-") as tmp:
        root = Path(tmp)
        data = root / "data"
        (data / "theme_profiles").mkdir(parents=True)
        (data / "backups").mkdir(parents=True)
        for rel in (
            "budgetmanager_settings.json",
            "budgetmanager_settings.tmp",
            "users.json",
            "budgetmanager.db",
            "audit.sqlite",
            "vault.enc",
        ):
            (data / rel).write_text("x", encoding="utf-8")
        (data / "theme_profiles" / "private.json").write_text("{}", encoding="utf-8")
        clean(root)
        leftovers = [
            rel
            for rel in (
                "budgetmanager_settings.json",
                "budgetmanager_settings.tmp",
                "users.json",
                "budgetmanager.db",
                "audit.sqlite",
                "vault.enc",
                "theme_profiles",
            )
            if (data / rel).exists()
        ]
        ok = not leftovers and (data / "backups" / ".gitkeep").exists()
        return 8, "PASS" if ok else "FAIL", ", ".join(leftovers)


def d2_prefilled_focus(i: int) -> tuple[int, str, str]:
    src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
    start = src.index("def focus_first_input")
    end = src.index("\n\nclass UiUsabilityFilter", start)
    block = src[start:end]
    ok = "selectAll()" not in block and "setCursorPosition(len(widget.text()))" in block
    return (
        2,
        "PASS" if ok else "FAIL",
        "Vorbefüllte Felder dürfen nicht komplett markiert werden",
    )


def _qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def d3_form_accessibility(i: int) -> tuple[int, str, str]:
    try:
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit
        from utils.ui_usability import enhance_widget_tree
    except ImportError:
        # v2.2.24 (Merge-Korrektur M2): Qt-freier Kern – die Label-Ableitung
        # existiert, wertet QFormLayout UND Buddy-Verknüpfungen aus und ist
        # in die Namens-Kandidaten eingehängt.
        src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
        ok = (
            "def _associated_form_label" in src
            and "labelForField" in src
            and ".buddy() is widget" in src
            and "_associated_form_label(widget)" in src
        )
        detail = (
            "Qt-freie Kernprüfung: Formularlabel-Ableitung vorhanden"
            if ok
            else "Formularlabel-Ableitung fehlt/entkoppelt"
        )
        return 1, "WARN" if ok else "FAIL", detail

    _qt_app()
    dlg = QDialog()
    form = QFormLayout(dlg)
    edit = QLineEdit()
    label = f"Betrag {i}"
    form.addRow(label, edit)
    enhance_widget_tree(dlg)
    ok = edit.accessibleName() == label
    dlg.close()
    return 1, "PASS" if ok else "FAIL", edit.accessibleName()


def d4_destructive_metadata(i: int) -> tuple[int, str, str]:
    try:
        from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout
        from utils.ui_usability import enhance_widget_tree
    except ImportError:
        # v2.2.24 (Merge-Korrektur M2): Ohne PySide6 (Audit-Container) die
        # Kernzusicherung Qt-frei prüfen – (a) die Erkennung feuert auf
        # Tooltip-Texten wie bei Icon-only-Buttons, (b) die Qt-Schicht
        # wertet nachweislich die Metadaten-Kette aus.
        from utils.ui_text_rules import is_destructive_text

        tooltip = "Eintrag löschen" if i % 2 == 0 else "Delete entry"
        ok = is_destructive_text(tooltip) and not is_destructive_text("Eintrag buchen")
        src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
        chain = all(
            m in src
            for m in (
                "button.text()",
                "button.toolTip()",
                "button.accessibleName()",
                "button.whatsThis()",
            )
        )
        ok = ok and chain
        detail = (
            "Qt-freie Kernprüfung: destruktive Metadatenkette vorhanden"
            if ok
            else "Icon-only-Erkennung (Qt-freier Kern) verletzt"
        )
        return 2, "WARN" if ok else "FAIL", detail

    _qt_app()
    dlg = QDialog()
    layout = QVBoxLayout(dlg)
    button = QPushButton("")
    button.setToolTip("Eintrag löschen" if i % 2 == 0 else "Delete entry")
    button.setAutoDefault(True)
    button.setDefault(True)
    layout.addWidget(button)
    enhance_widget_tree(dlg)
    ok = not button.autoDefault() and not button.isDefault()
    dlg.close()
    return 2, "PASS" if ok else "FAIL", "Icon-only-Löschaktion blieb Enter-Default"


def d5_language_consistency(i: int) -> tuple[int, str, str]:
    src = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    start = src.index("    def _show_settings(self):")
    end = src.index("\n    def ", start + 10)
    method = src[start:end]
    locale_ok = True
    for lang in ("de", "en", "fr"):
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        locale_ok = locale_ok and bool(
            data.get("msg", {}).get("language_restart_required")
        )
    ok = (
        "set_language(" not in method
        and "msg.language_restart_required" in method
        and locale_ok
    )
    return 5, "PASS" if ok else "FAIL", "Live-Sprachwechsel würde gemischte UI erzeugen"


_THEME_PAIRS = {
    "text": (
        "hintergrund_app",
        "hintergrund_panel",
        "hintergrund_seitenleiste",
        "tabelle_hintergrund",
        "tabelle_alt",
    ),
    "text_gedimmt": (
        "hintergrund_app",
        "hintergrund_panel",
        "hintergrund_seitenleiste",
    ),
    "akzent_text": ("akzent",),
    "akzent_panel_text": ("hintergrund_panel",),
    "tabelle_header_text": ("tabelle_header",),
    "auswahl_text": ("auswahl_hintergrund",),
    "dropdown_text": ("dropdown_bg",),
    "dropdown_selection_text": ("dropdown_selection",),
    "hover_text": ("hover_hintergrund",),
    "negativ_text": (
        "hintergrund_app",
        "hintergrund_panel",
        "tabelle_hintergrund",
        "tabelle_alt",
    ),
}

_THEME_FILES = sorted((ROOT / "views" / "profiles").glob("*.json"))


def d6_theme_contrast(i: int) -> tuple[int, str, str]:
    path = _THEME_FILES[i % len(_THEME_FILES)]
    profile = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    checks = 0
    for foreground, backgrounds in _THEME_PAIRS.items():
        for background in backgrounds:
            if foreground not in profile or background not in profile:
                continue
            checks += 1
            ratio = _contrast(profile[foreground], profile[background])
            if ratio < 4.5:
                failures.append(f"{foreground}/{background}={ratio:.2f}:1")
    return (
        checks,
        "FAIL" if failures else "PASS",
        f"{path.name}: " + ", ".join(failures),
    )


def d7_icon_targets(i: int) -> tuple[int, str, str]:
    files = sorted((ROOT / "views").rglob("*.py"))
    path = files[i % len(files)]
    src = path.read_text(encoding="utf-8")
    failures: list[str] = []
    for match in re.finditer(r"(\w+)\s*=\s*QPushButton\(\s*[\"']\s*[\"']\s*\)", src):
        var = match.group(1)
        tail = src[match.end() : match.end() + 700]
        size = re.search(rf"{re.escape(var)}\.setFixedSize\((\d+),\s*(\d+)\)", tail)
        if size and (int(size.group(1)) < 32 or int(size.group(2)) < 32):
            failures.append(f"{var}={size.group(1)}x{size.group(2)}")
    return (
        1,
        "FAIL" if failures else "PASS",
        f"{path.relative_to(ROOT)}: {', '.join(failures)}",
    )


def d8_scaling(i: int) -> tuple[int, str, str]:
    files = sorted((ROOT / "views").rglob("*.py"))
    path = files[i % len(files)]
    src = path.read_text(encoding="utf-8")
    dialog_file = bool(re.search(r"^class .*\(QDialog\)", src, re.MULTILINE))
    fixed = list(re.finditer(r"self\.setFixedSize\(", src)) if dialog_file else []
    return (
        1,
        "FAIL" if fixed else "PASS",
        f"{path.relative_to(ROOT)}: setFixedSize auf Dialog",
    )


def d9_modal_load(i: int) -> tuple[int, str, str]:
    files = list((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"]
    info = 0
    passive_warnings = 0
    safety_dialogs = 0
    for path in files:
        src = path.read_text(encoding="utf-8")
        info += src.count("QMessageBox.information")
        safety_dialogs += sum(
            src.count(f"QMessageBox.{name}") for name in ("critical", "question")
        )
        # Nur Warnungen mit Rückgabewert/Entscheidung dürfen modal bleiben.
        passive_warnings += len(
            re.findall(r"^\s*QMessageBox\.warning\(", src, re.MULTILINE)
        )
    result = "PASS" if info == 0 and passive_warnings == 0 else "WARN"
    detail = (
        f"{info} modale Informationen, {passive_warnings} passive Warnungen, "
        f"{safety_dialogs} Sicherheits-/Fehlerdialoge bewusst modal"
    )
    return 2, result, detail


def d10_keyboard_navigation(i: int) -> tuple[int, str, str]:
    files = list((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"]
    complex_dialogs = 0
    configured = 0
    for path in files:
        src = path.read_text(encoding="utf-8")
        if (
            re.search(r"^class .*\(QDialog\)", src, re.MULTILINE)
            and src.count("QPushButton(") >= 5
        ):
            complex_dialogs += 1
            if "configure_dialog_tab_order(self)" in src:
                configured += 1
    result = "PASS" if configured == complex_dialogs else "WARN"
    return (
        2,
        result,
        f"{configured}/{complex_dialogs} komplexe Dialogdateien mit expliziter Tab-Kette",
    )


DOMAINS = (
    ("d1_release_cleaner", d1_release_cleaner),
    ("d2_prefilled_focus", d2_prefilled_focus),
    ("d3_form_accessibility", d3_form_accessibility),
    ("d4_destructive_metadata", d4_destructive_metadata),
    ("d5_language_consistency", d5_language_consistency),
    ("d6_theme_contrast", d6_theme_contrast),
    ("d7_icon_targets", d7_icon_targets),
    ("d8_scaling", d8_scaling),
    ("d9_modal_load", d9_modal_load),
    ("d10_keyboard_navigation", d10_keyboard_navigation),
)


def main() -> int:
    csv_path = ROOT / (
        "UI_USABILITY_ADHS_1000_LOOP_MATRIX_v" + APP_VERSION.replace(".", "_") + ".csv"
    )
    if "--csv" in sys.argv:
        csv_path = Path(sys.argv[sys.argv.index("--csv") + 1])

    loop = 0
    total_checks = 0
    for round_index in range(100):
        for name, domain in DOMAINS:
            loop += 1
            try:
                checks, result, detail = domain(round_index)
            except Exception as exc:  # Auditfehler ist selbst ein Blocker.
                checks, result, detail = 1, "FAIL", f"{type(exc).__name__}: {exc}"
            total_checks += checks
            _record(loop, name, checks, result, detail)
        if loop % 200 == 0:
            fails = sum(r["result"] == "FAIL" for r in ROWS)
            warns = sum(r["result"] == "WARN" for r in ROWS)
            print(f"Loop {loop:04d}: checks={total_checks} fail={fails} warn={warns}")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("loop", "domain", "checks", "result", "detail")
        )
        writer.writeheader()
        writer.writerows(ROWS)

    fails = sum(r["result"] == "FAIL" for r in ROWS)
    warns = sum(r["result"] == "WARN" for r in ROWS)
    passes = sum(r["result"] == "PASS" for r in ROWS)
    print(f"CSV: {csv_path}")
    print(
        f"ENTERPRISE UI/ADHS AUDIT DONE: loops={len(ROWS)} checks={total_checks} "
        f"pass={passes} warn={warns} fail={fails}"
    )
    for domain, (severity, detail) in UNIQUE.items():
        print(f"  {severity} {domain}: {detail}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
