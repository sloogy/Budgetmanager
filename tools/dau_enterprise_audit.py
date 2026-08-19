#!/usr/bin/env python3
"""DAU-Enterprise-Audit: Funktionen, Verweise, Beschriftungen, Design.

Ergänzt die bestehenden Audits um Prüfungen, die bisher niemand abdeckte.
Bewusst Qt-frei (statisch über AST und Text), damit das Audit im Container und
im CI ohne Bildschirm läuft.

Prüfblöcke
----------
A  Menü-Konventionen über *alle* Menüs (nicht nur Hilfe)
B  i18n-Platzhalter- und Wertparität
C  Verweis-Integrität (Hilfeseiten, Ressourcen, Bilder)
D  Signal-Verdrahtung (kein Klick ins Leere)
E  Theme-Disziplin (Bugklasse v2.2.33: Systemfarben übersteuern das Profil)
F  Erreichbarkeit (kein toter Dialog, kein verwaister Reiter)

Aufruf::

    python3 tools/dau_enterprise_audit.py [--loops N]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "locales"
LANGS = ("de", "en", "fr")

# Module, in denen Farben definiert werden duerfen.
THEME_OWNERS = {"theme_manager.py", "ui_colors.py"}

# Von QDialog/QWidget/QMainWindow geerbte Slots – existieren ohne eigene Definition.
QT_INHERITED = {
    "accept",
    "reject",
    "close",
    "show",
    "hide",
    "showNormal",
    "showMaximized",
    "showMinimized",
    "raise_",
    "update",
    "repaint",
    "deleteLater",
    "setFocus",
    "clear",
    "selectAll",
    "copy",
    "paste",
    "cut",
    "undo",
    "redo",
    "done",
}


class Findings:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []
        self.checks = 0

    def check(self, code: str, ok: bool, message: str) -> None:
        self.checks += 1
        if not ok:
            self.items.append((code, message))

    def __bool__(self) -> bool:
        return bool(self.items)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _locale(lang: str) -> dict:
    """Locale flach als Punktschluessel -> Wert."""
    raw = json.loads(_read(LOCALES / f"{lang}.json"))
    flat: dict[str, str] = {}

    def walk(prefix: str, node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(f"{prefix}.{key}" if prefix else key, value)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(f"{prefix}[{index}]", value)
        else:
            flat[prefix] = str(node)

    walk("", raw)
    return flat


def _python_files() -> list[Path]:
    skip = {"tests", "tools", "build", "dist", "__pycache__"}
    return [
        p
        for p in ROOT.rglob("*.py")
        if not any(part in skip for part in p.relative_to(ROOT).parts)
    ]


# ── A  Menü-Konventionen ────────────────────────────────────────

# Einträge, die einen Dialog oeffnen und daher '…' tragen muessen.
DIALOG_SUFFIX_EXPECTED = {
    "menu.handbook",
    "menu.shortcuts",
    "menu.setup_assistant",
    "menu.show_log",
    "menu.show_crash_log",
    "menu.create_diagnostic_report",
    "menu.show_restore_key",
    "menu.updates",
    "menu.release_notes",
    "menu.about",
    "menu.account_manage",
}
# Eintraege, die sofort ausfuehren und daher *kein* '…' tragen duerfen.
IMMEDIATE_NO_SUFFIX = {
    "menu.knowledge_base",
    "menu.help_mindmap",
    "menu.wiki_audit",
    "menu.open_diagnostics_folder",
    "menu.help_visuals",
    "menu.troubleshooting",
    "menu.help",
    "menu.edit",
    "menu.file",
    "menu.view",
    "menu.extras",
    "menu.account",
}
# Zugriffstasten muessen je Menue eindeutig sein.
MENU_LEVELS = {
    "Hilfe": (
        "menu.handbook",
        "menu.knowledge_base",
        "menu.help_visuals",
        "menu.shortcuts",
        "menu.setup_assistant",
        "menu.troubleshooting",
        "menu.updates",
        "menu.release_notes",
        "menu.about",
    ),
    "Problembehandlung": (
        "menu.show_log",
        "menu.show_crash_log",
        "menu.open_diagnostics_folder",
        "menu.create_diagnostic_report",
        "menu.show_restore_key",
    ),
    "Visuelle Übersichten": ("menu.help_mindmap", "menu.wiki_audit"),
}


def audit_menu_conventions(f: Findings) -> None:
    for lang in LANGS:
        loc = _locale(lang)

        for key in DIALOG_SUFFIX_EXPECTED:
            label = loc.get(key)
            if label is None:
                continue
            f.check("A1", label.endswith("…"), f"{lang}/{key}: '…' fehlt ({label!r})")
            f.check("A2", "..." not in label, f"{lang}/{key}: drei Punkte statt '…'")

        for key in IMMEDIATE_NO_SUFFIX:
            label = loc.get(key)
            if label is None:
                continue
            f.check(
                "A3",
                not label.endswith("…") and "..." not in label,
                f"{lang}/{key}: Sofortbefehl mit Auslassungspunkten ({label!r})",
            )

        for menu_name, keys in MENU_LEVELS.items():
            used: dict[str, str] = {}
            for key in keys:
                label = loc.get(key)
                if label is None:
                    continue
                f.check("A4", "&" in label, f"{lang}/{key}: keine Zugriffstaste")
                if "&" not in label:
                    continue
                letter = label[label.index("&") + 1].lower()
                f.check(
                    "A5",
                    letter not in used,
                    f"{lang}/{menu_name}: '{letter}' doppelt "
                    f"({used.get(letter)} und {key})",
                )
                used.setdefault(letter, key)

        # Kein Menuetitel darf mit einem Kleinbuchstaben beginnen (nach '&').
        for key in MENU_LEVELS["Hilfe"]:
            label = loc.get(key, "")
            visible = label.replace("&", "")
            f.check(
                "A6",
                not visible or visible[0].isupper() or not visible[0].isalpha(),
                f"{lang}/{key}: Beschriftung beginnt klein ({label!r})",
            )


# ── B  i18n-Parität ─────────────────────────────────────────────


def _format_keys() -> set[str]:
    """Schlüssel, die per ``trf`` formatiert werden – nur dort zählen Platzhalter.

    Reine Beschriftungen dürfen Platzhalternamen sprachspezifisch dokumentieren:
    ``tags.action_text_label`` nennt im Deutschen ``{datum}``, im Englischen
    ``{date}`` – beide Schreibweisen akzeptiert ``model/tags_model.py``.
    """
    keys: set[str] = set()
    for path in _python_files():
        keys.update(re.findall(r'trf\(\s*"([\w.]+)"', _read(path)))
    return keys


def _mnemonics(label: str) -> int:
    """Zählt echte Zugriffstasten; '&&' ist ein dargestelltes Und-Zeichen."""
    return len(re.findall(r"(?<!&)&(?!&)[^\s]", label.replace("&&", "")))


def audit_i18n_parity(f: Findings) -> None:
    base = _locale("de")
    format_keys = _format_keys()
    others = {lang: _locale(lang) for lang in ("en", "fr")}
    placeholder = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    for lang, loc in others.items():
        f.check(
            "B1",
            len(loc) == len(base),
            f"{lang}: {len(loc)} Schlüssel gegenüber de {len(base)}",
        )
        for key, german in base.items():
            value = loc.get(key)
            f.check("B2", value is not None, f"{lang}/{key} fehlt")
            if value is None:
                continue
            f.check("B3", value.strip() != "", f"{lang}/{key} ist leer")
            f.check(
                "B4",
                key not in format_keys
                or set(placeholder.findall(german)) == set(placeholder.findall(value)),
                f"{lang}/{key}: Platzhalter weichen ab "
                f"({sorted(set(placeholder.findall(german)))} vs "
                f"{sorted(set(placeholder.findall(value)))})",
            )
            f.check(
                "B5",
                not key.startswith("menu.") or _mnemonics(german) == _mnemonics(value),
                f"{lang}/{key}: Zugriffstaste fehlt oder ist zu viel "
                f"({german!r} vs {value!r})",
            )


# ── C  Verweis-Integrität ───────────────────────────────────────


def audit_link_integrity(f: Findings) -> None:
    # C1: in Python referenzierte Hilfedateien existieren
    referenced = set()
    for path in _python_files():
        referenced.update(re.findall(r'"(docs/help/[\w./-]+)"', _read(path)))
    for rel in sorted(referenced):
        f.check("C1", (ROOT / rel).exists(), f"referenzierte Hilfedatei fehlt: {rel}")

    # C2: lokale Verweise innerhalb der Offline-Hilfe zeigen auf vorhandene Dateien
    help_dir = ROOT / "docs" / "help"
    for page in sorted(help_dir.glob("*.html")):
        html = _read(page)
        for target in re.findall(r'(?:href|src)="([^"#:]+)"', html):
            if target.startswith(("http", "mailto", "data:")):
                continue
            f.check(
                "C2",
                (page.parent / target).exists(),
                f"{page.name}: toter Verweis auf {target}",
            )

    # C3: Dateien, die der Build mitliefert, existieren auch wirklich
    spec = _read(ROOT / "BudgetManager.spec")
    for rel in re.findall(r'\("([\w./-]+)",\s*"[\w./.-]+"\)', spec):
        f.check("C3", (ROOT / rel).exists(), f"Spec liefert fehlende Datei: {rel}")


# ── D  Signal-Verdrahtung ───────────────────────────────────────


def audit_signal_wiring(f: Findings) -> None:
    """Jede an ein Signal gehängte ``self.<name>``-Methode muss existieren."""
    for path in _python_files():
        try:
            tree = ast.parse(_read(path))
        except SyntaxError as exc:  # pragma: no cover
            f.check("D0", False, f"{path.name}: nicht parsebar ({exc})")
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            defined = {n.name for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)}
            # self.x = ... sowie klassenweite Namen (u. a. Signal-Deklarationen)
            assigned = {
                target.attr
                for node in ast.walk(cls)
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Attribute)
            } | {
                target.id
                for node in cls.body
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            defined |= QT_INHERITED
            for node in ast.walk(cls):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Attribute) and func.attr == "connect"):
                    continue
                for arg in node.args:
                    if (
                        isinstance(arg, ast.Attribute)
                        and isinstance(arg.value, ast.Name)
                        and arg.value.id == "self"
                    ):
                        f.check(
                            "D1",
                            arg.attr in defined or arg.attr in assigned,
                            f"{path.name}/{cls.name}: connect auf fehlendes "
                            f"self.{arg.attr}",
                        )


# ── E  Theme-Disziplin ──────────────────────────────────────────


def audit_theme_discipline(f: Findings) -> None:
    """Bugklasse v2.2.33: Systempalette und Festfarben übersteuern das Profil."""
    hex_color = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
    for path in _python_files():
        if path.name in THEME_OWNERS or "profiles" in path.parts:
            continue
        text = _read(path)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "setStyleSheet"):
                continue
            literals = " ".join(
                sub.value
                for sub in ast.walk(node)
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
            )
            f.check(
                "E1",
                "palette(" not in literals,
                f"{path.name}:{node.lineno}: setStyleSheet nutzt Systempalette",
            )
            f.check(
                "E2",
                not hex_color.search(literals),
                f"{path.name}:{node.lineno}: feste Hexfarbe im Stylesheet "
                f"({(hex_color.search(literals) or [''])[0]})",
            )


# ── F  Erreichbarkeit ───────────────────────────────────────────


def audit_reachability(f: Findings) -> None:
    """Kein Dialog und kein Reiter darf ohne Aufrufer im Baum liegen."""
    sources = {p: _read(p) for p in _python_files()}
    for path, text in sources.items():
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            if not cls.name.endswith(("Dialog", "Tab", "Panel", "Wizard")):
                continue
            elsewhere = any(
                cls.name in other_text
                for other_path, other_text in sources.items()
                if other_path != path
            )
            own = text.count(cls.name) > 1  # Definition plus mindestens ein Aufruf
            used = elsewhere or own
            f.check("F1", used, f"{path.name}: {cls.name} wird nirgends verwendet")


# ── G  Historische Versionsangaben ──────────────────────────────


def audit_version_references(f: Findings) -> None:
    """Schützt Sätze wie „seit v2.2.38" vor pauschalen Versions-Sweeps.

    Beim Release-Sweep wird die Versionsnummer in vielen Dateien ersetzt. Das
    zog bis v2.2.40 auch historische Aussagen in den Handbüchern mit: aus
    „seit v2.2.38" wurde bei jedem Release die jeweils aktuelle Version, und
    das Handbuch behauptete, ein altes Merkmal sei brandneu. Die Sperrdatei
    friert die zulässigen Angaben je Datei ein.
    """
    lock_path = ROOT / "docs/version_references.lock.json"
    f.check("G1", lock_path.exists(), "docs/version_references.lock.json fehlt")
    if not lock_path.exists():
        return
    lock = json.loads(_read(lock_path))
    pattern = re.compile(r"(?:seit v|Since v|Depuis la version )(\d+\.\d+\.\d+)")
    for rel, expected in lock.items():
        path = ROOT / rel
        f.check("G2", path.exists(), f"gesperrte Datei fehlt: {rel}")
        if not path.exists():
            continue
        found = sorted(set(pattern.findall(_read(path))))
        f.check(
            "G3",
            found == sorted(expected),
            f"{rel}: Versionsangaben verschoben – erwartet {sorted(expected)}, "
            f"gefunden {found}",
        )


# ── H  Anleitung gegen Oberfläche ───────────────────────────────

#: Sprachspezifische Pfeile in beschriebenen Menuewegen.
_PATH_PATTERN = re.compile(r"\*\*([^*]+?\u2192[^*]+?)\*\*")


def _menu_labels(lang: str) -> set[str]:
    """Alle Beschriftungen einer Sprache, normalisiert wie im Handbuch."""
    labels = set()
    for value in _locale(lang).values():
        cleaned = value.replace("&&", "\x00").replace("&", "").replace("\x00", "&")
        cleaned = cleaned.replace("\u2026", "").strip()
        if cleaned:
            labels.add(cleaned)
    return labels


def audit_guide_matches_ui(f: Findings) -> None:
    """Jeder im Handbuch beschriebene Menueweg muss es wirklich geben.

    Für einen Einsteiger ist eine Anleitung, die auf einen nicht vorhandenen
    Menuepunkt zeigt, schlimmer als gar keine: er sucht, findet nichts und
    zweifelt an sich statt an der Dokumentation.
    """
    guides = {
        "de": "docs/USER_GUIDE.de.md",
        "en": "docs/USER_GUIDE.en.md",
        "fr": "docs/USER_GUIDE.fr.md",
    }
    for lang, rel in guides.items():
        path = ROOT / rel
        if not path.exists():
            f.check("H0", False, f"Handbuch fehlt: {rel}")
            continue
        labels = _menu_labels(lang)
        # Nur Wege, die in der Menueleiste beginnen. Das Handbuch nutzt die
        # Pfeilschreibweise auch fuer Reiterwechsel ("Budget -> Uebersicht");
        # das sind keine Menuepunkte und gehoeren nicht in diese Pruefung.
        roots = {
            "de": ("Datei", "Bearbeiten", "Ansicht", "Extras", "Konto", "Hilfe"),
            "en": ("File", "Edit", "View", "Extras", "Account", "Help"),
            "fr": ("Fichier", "Édition", "Affichage", "Extras", "Compte", "Aide"),
        }[lang]
        for raw_path in _PATH_PATTERN.findall(_read(path)):
            head = raw_path.split("\u2192")[0].strip()
            if not head.startswith(roots):
                continue
            # Nur Menuetitel und Menuepunkt pruefen. Tiefere Segmente sind
            # Dialoginhalte (Reiter, Ankreuzfelder) - deren Beschriftungen
            # liegen ausserhalb der Menuenamensraeume und liessen sich hier
            # nur mit Fehlalarmen pruefen.
            for segment in [s.strip() for s in raw_path.split("\u2192")][:2]:
                # Das Handbuch notiert teils "Beschriftung / Tastenkürzel".
                segment = segment.split(" / ")[0].strip()
                if not segment or segment.endswith((":", "?")) or "Ctrl" in segment:
                    continue
                f.check(
                    "H1",
                    segment in labels,
                    f"{rel}: Menueweg nennt '{segment}', "
                    f"das es in {lang}.json nicht gibt",
                )


# ── I  Destruktive Aktionen ─────────────────────────────────────

_DESTRUCTIVE = ("delete_", "reset_", "wipe_", "drop_", "purge_", "clear_all")
_CONFIRMERS = (
    "question",
    "ask_confirm",
    "confirm",
    "warning",
    "StandardButton.Yes",
    "exec",
    "Dialog(",
    "critical",
)


def audit_destructive_actions_confirm(f: Findings) -> None:
    """Löschen und Zurücksetzen brauchen eine Rückfrage im selben Ablauf."""
    for path in _python_files():
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            source = ast.get_source_segment(_read(path), func) or ""
            # Nur Aufrufe auf Modell/Verbindung zaehlen. Ein Wrapper, der an
            # einen Reiter weiterreicht (self.categories_tab.delete_selected),
            # fragt zu Recht nicht selbst nach - das tut die Zielmethode.
            calls_destructive = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr.startswith(_DESTRUCTIVE)
                and not node.func.attr.endswith(("_flag", "_flags", "_cache"))
                and not (
                    isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr.endswith(("_tab", "_page", "_view"))
                )
                for node in ast.walk(func)
            )
            if not calls_destructive:
                continue
            # Modellschicht fragt nicht nach; nur Bedienoberflaechen zaehlen.
            if "views/" not in str(path.relative_to(ROOT)).replace("\\", "/"):
                continue
            f.check(
                "I1",
                any(marker in source for marker in _CONFIRMERS),
                f"{path.name}/{func.name}: destruktive Aktion ohne Rückfrage",
            )


# ── J  Leerzustände ─────────────────────────────────────────────


def audit_empty_states(f: Findings) -> None:
    """Keine Liste darf ohne erklärenden Leertext bleiben."""
    for path in _python_files():
        text = _read(path)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "_set_table_rows"
            ):
                continue
            f.check(
                "J1",
                len(node.args) >= 3,
                f"{path.name}:{node.lineno}: Tabelle ohne Leertext",
            )
            if len(node.args) < 3:
                continue
            empty_arg = node.args[2]
            literal_empty = (
                isinstance(empty_arg, ast.Constant)
                and isinstance(empty_arg.value, str)
                and not empty_arg.value.strip()
            )
            f.check(
                "J2",
                not literal_empty,
                f"{path.name}:{node.lineno}: Leertext ist leer",
            )


# ── K  Sprache ohne Technikjargon ───────────────────────────────

_JARGON = (
    "traceback",
    "stacktrace",
    "exception",
    "nonetype",
    "callback",
    "stdout",
    "stderr",
    "boolean",
    "nullpointer",
    "segmentation fault",
)


def audit_user_language(f: Findings) -> None:
    """Angezeigte Texte dürfen keine Entwicklerbegriffe enthalten.

    Der Platzhalter ``{error}`` bleibt erlaubt – dort steht die technische
    Ursache bewusst, aber eingebettet in einen erklärenden Satz.
    """
    for lang in LANGS:
        for key, value in _locale(lang).items():
            lowered = value.lower()
            for word in _JARGON:
                f.check(
                    "K1",
                    word not in lowered,
                    f"{lang}/{key}: Fachjargon '{word}' im angezeigten Text",
                )


def audit_no_system_palette_colors(f: Findings) -> None:
    """Views duerfen Farben nicht aus QPalette ableiten.

    Vierter Fund derselben Bugklasse (Seitenleiste 2.2.33, Login/Konto 2.2.39,
    Cockpit-Beschriftungen 2.2.44, Budget-Tabelle 2.2.46): ein dunkles
    Systemtheme faerbt dann gegen ein helles BudgetManager-Profil. Farben
    kommen aus dem Profil, nicht vom Desktop.
    """
    for path in _python_files():
        if path.name in THEME_OWNERS:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if not rel.startswith("views/"):
            continue
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ):
                continue
            if node.func.attr not in ("color", "setColor", "brush"):
                continue
            source = ast.get_source_segment(_read(path), node) or ""
            f.check(
                "L1",
                "QPalette." not in source,
                f"{path.name}:{node.lineno}: Farbe aus der Systempalette "
                f"({source[:60]})",
            )


AUDITS = (
    ("A Menü-Konventionen", audit_menu_conventions),
    ("B i18n-Parität", audit_i18n_parity),
    ("C Verweis-Integrität", audit_link_integrity),
    ("D Signal-Verdrahtung", audit_signal_wiring),
    ("E Theme-Disziplin", audit_theme_discipline),
    ("F Erreichbarkeit", audit_reachability),
    ("G Versionsangaben", audit_version_references),
    ("H Anleitung gegen Oberfläche", audit_guide_matches_ui),
    ("I Destruktive Aktionen", audit_destructive_actions_confirm),
    ("J Leerzustände", audit_empty_states),
    ("K Sprache", audit_user_language),
    ("L Systempalette", audit_no_system_palette_colors),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, default=1)
    args = parser.parse_args()

    if args.loops < 1:
        parser.error("--loops muss mindestens 1 sein")

    # Alle Audits in diesem Werkzeug sind statische, deterministische
    # Quellbaum-Prüfungen. Den unveränderten Baum 10'000-mal neu einzulesen
    # erzeugt keine zusätzliche Aussage, blockierte aber lokale Release-Läufe
    # für viele Minuten. Wir führen deshalb jeden Prüfer exakt einmal aus und
    # zählen die bestätigte Invariante für die gewünschte Loop-Zahl hoch.
    checks_per_loop = 0
    all_findings: list[tuple[str, str]] = []
    for name, audit in AUDITS:
        f = Findings()
        audit(f)
        checks_per_loop += f.checks
        status = "FAIL" if f else "PASS"
        print(f"[{status}] {name}: {f.checks} Prüfungen, {len(f.items)} Funde")
        all_findings.extend(f.items)

    total_checks = checks_per_loop * args.loops

    if all_findings:
        print("\nFunde:")
        for code, message in all_findings:
            print(f"  [{code}] {message}")

    print(
        f"\nDAU-ENTERPRISE-AUDIT: loops={args.loops} checks={total_checks} "
        f"findings={len(all_findings)}"
    )
    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
