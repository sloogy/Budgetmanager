"""Regressionstests v2.2.33 – Seitenleiste folgt dem App-Theme.

Befund (vom Nutzer gemeldet): Bei aktivem hellem Profil ("V2 Hell – Neon Cyan")
blieb die linke Navigationsleiste dunkel.

Ursachenkette:
1. ``ThemeManager.apply_theme()`` setzt ausschliesslich ``app.setStyleSheet()``
   und **nie** ``app.setPalette()``.
2. ``MainWindow._apply_modern_shell_style()`` faerbte die Seitenleiste aber mit
   ``palette(base)``/``palette(highlight)``/``palette(text)``. Diese loesen
   gegen die **System**-Palette auf – auf einem dunklen Desktop also dunkel.
3. ``QFrame#mainSidebar`` ist ein spezifischerer Selektor als das generische
   ``QWidget`` des App-Themes und gewann deshalb.
4. Der in allen 25 Profilen vorhandene und im Erscheinungsmanager
   einstellbare Schluessel ``hintergrund_seitenleiste`` wurde von keinem
   Widget gerendert – er war faktisch wirkungslos.

Zusaetzlich behoben: ``_apply_modern_shell_style`` hing seinen Block per
``setStyleSheet(self.styleSheet() + ...)`` an und laeuft bei *jedem*
Theme-Wechsel erneut → das Stylesheet wuchs unbegrenzt.

Hinweis zur Testtechnik: Diese Tests arbeiten rein statisch ueber den AST.
``build_stylesheet`` wird **nicht** ausgefuehrt – PySide6 fehlt im
Release-Container, und ``exec()`` ist durch den Security-Lint des Projekts
untersagt. Das Stylesheet-Template wird stattdessen aus dem f-String-Knoten
rekonstruiert.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAIN_WINDOW = ROOT / "views" / "main_window.py"
THEME_MANAGER = ROOT / "theme_manager.py"
PROFILES_DIR = ROOT / "views" / "profiles"

SIDEBAR_SELECTORS = (
    "QFrame#mainSidebar",
    "QLabel#sidebarBrand",
    "QLabel#sidebarVersion",
    "QPushButton#sidebarNavButton",
)


# ────────────────────────────────────────────────────────────────
# Hilfsfunktionen (rein statisch)
# ────────────────────────────────────────────────────────────────


def _find_function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} nicht gefunden in {path.name}")


def _body_string_literals(func: ast.FunctionDef) -> str:
    """String-Literale einer Funktion – **ohne** ihren Docstring.

    ``ast.get_docstring()`` liefert den *bereinigten* Text und ist daher nicht
    identisch mit dem rohen Constant-Wert; der Docstring muss ueber seine
    Position (erstes Statement) ausgeschlossen werden, sonst schlagen diese
    Tests am eigenen Erklaertext fehl.
    """
    body = func.body
    has_doc = (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
    out: list[str] = []
    for stmt in body[1:] if has_doc else body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append(node.value)
    return "\n".join(out)


def _stylesheet_template() -> str:
    """Rekonstruiert das QSS-Template aus dem f-String von build_stylesheet.

    Platzhalter erscheinen als ``{variablenname}`` – ohne Ausfuehrung.
    """
    func = _find_function(THEME_MANAGER, "build_stylesheet")
    for node in ast.walk(func):
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    parts.append("{" + ast.unparse(value.value) + "}")
            template = "".join(parts)
            if "QFrame#mainSidebar" in template:
                return template
    raise AssertionError("Stylesheet-Template mit Sidebar-Regeln nicht gefunden")


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _all_profiles():
    for path in sorted(PROFILES_DIR.glob("*.json")):
        yield path.name, json.loads(path.read_text(encoding="utf-8"))


def _relative_luminance(hexcode: str) -> float:
    r, g, b = (int(hexcode[i : i + 2], 16) for i in (1, 3, 5))
    channels = []
    for raw in (r, g, b):
        srgb = raw / 255
        channels.append(
            srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


# ────────────────────────────────────────────────────────────────
# Kernregression: keine System-Palette für die Seitenleiste
# ────────────────────────────────────────────────────────────────


def test_shell_style_sets_no_colors_at_all():
    """Der Shell-Style darf nur Geometrie liefern, keine Farben.

    Sobald hier wieder Farben gesetzt werden, uebersteuern sie das App-Theme
    (spezifischerer Selektor) und der Bug ist zurueck.
    """
    css = _body_string_literals(
        _find_function(MAIN_WINDOW, "_apply_modern_shell_style")
    )
    assert "palette(" not in css, "System-Palette im Shell-Style (Regression v2.2.32)"
    for forbidden in ("background:", "background-color:", "color:"):
        assert forbidden not in css, f"Farbangabe '{forbidden}' gehört ins Theme"


def test_shell_style_still_defines_layout():
    css = _body_string_literals(
        _find_function(MAIN_WINDOW, "_apply_modern_shell_style")
    )
    for needed in ("QLabel#sidebarBrand", "border-radius", "padding"):
        assert needed in css, f"Strukturregel '{needed}' fehlt"


def test_shell_style_does_not_accumulate():
    """setStyleSheet darf das Stylesheet nicht an sich selbst anhängen."""
    func = _find_function(MAIN_WINDOW, "_apply_modern_shell_style")
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", "") == "setStyleSheet"
        ):
            assert not any(
                isinstance(arg, ast.BinOp) for arg in node.args
            ), "Stylesheet wird verkettet – wächst bei jedem Theme-Wechsel"


# ────────────────────────────────────────────────────────────────
# Das App-Theme färbt die Seitenleiste
# ────────────────────────────────────────────────────────────────


def test_theme_template_defines_sidebar_selectors():
    template = _stylesheet_template()
    for selector in SIDEBAR_SELECTORS:
        assert selector in template, f"{selector} fehlt im App-Stylesheet"


def test_theme_template_uses_no_system_palette():
    template = _strip_css_comments(_stylesheet_template())
    assert "palette(" not in template


def _sidebar_rule_line(template: str) -> str:
    """Die Zeile mit der ``QFrame#mainSidebar``-Regel.

    Bewusst zeilenweise statt per ``\\{([^}]*)\\}``: Die Platzhalter im
    Template (``{bg_sidebar}``) enthalten selbst geschweifte Klammern, an
    denen ein solcher Ausdruck vorzeitig endet.
    """
    for line in template.splitlines():
        stripped = line.strip()
        if stripped.startswith("QFrame#mainSidebar {"):
            return stripped
    raise AssertionError("keine mainSidebar-Regel im Template")


def test_sidebar_rule_is_fed_by_profile_key():
    """Die Sidebar-Regel muss den Profilwert verwenden, keinen Literalwert."""
    rule = _sidebar_rule_line(_stylesheet_template())
    assert (
        "background-color: {bg_sidebar}" in rule
    ), f"Sidebar-Hintergrund kommt nicht aus dem Profil: {rule!r}"
    assert not re.search(
        r"background-color:\s*#[0-9a-fA-F]{3,8}", rule
    ), f"fest verdrahtete Farbe in der Sidebar-Regel: {rule!r}"


def test_bg_sidebar_reads_the_profile_key():
    """bg_sidebar muss aus 'hintergrund_seitenleiste' stammen."""
    func = _find_function(THEME_MANAGER, "build_stylesheet")
    source = ast.unparse(func)
    match = re.search(r"bg_sidebar\s*=\s*p\.get\(\s*['\"]([^'\"]+)['\"]", source)
    assert match, "bg_sidebar wird nicht aus dem Profil gelesen"
    assert match.group(1) == "hintergrund_seitenleiste"


# ────────────────────────────────────────────────────────────────
# Profildaten: helles Profil ⇒ helle Leiste (das gemeldete Fehlerbild)
# ────────────────────────────────────────────────────────────────


def test_light_profiles_define_light_sidebar():
    for name, profile in _all_profiles():
        if profile.get("modus") != "hell":
            continue
        hexcode = profile["hintergrund_seitenleiste"]
        assert (
            _relative_luminance(hexcode) > 0.5
        ), f"{name}: helles Profil, aber dunkle Seitenleistenfarbe ({hexcode})"


def test_dark_profiles_define_dark_sidebar():
    for name, profile in _all_profiles():
        if profile.get("modus") == "hell":
            continue
        hexcode = profile["hintergrund_seitenleiste"]
        assert (
            _relative_luminance(hexcode) < 0.5
        ), f"{name}: dunkles Profil, aber helle Seitenleistenfarbe ({hexcode})"


def test_sidebar_text_contrast_is_readable():
    """Schrift auf der Leiste muss lesbar bleiben (WCAG AA für Fliesstext)."""
    for name, profile in _all_profiles():
        bg = profile["hintergrund_seitenleiste"]
        fg = profile["text"]
        if not (
            len(bg) == 7 and bg.startswith("#") and len(fg) == 7 and fg.startswith("#")
        ):
            continue
        light, dark = sorted(
            (_relative_luminance(bg), _relative_luminance(fg)), reverse=True
        )
        ratio = (light + 0.05) / (dark + 0.05)
        assert ratio >= 4.5, f"{name}: Kontrast Text/Seitenleiste nur {ratio:.1f}:1"


def test_all_profiles_define_sidebar_key():
    profiles = list(_all_profiles())
    assert profiles, "keine Profile gefunden"
    for name, profile in profiles:
        assert "hintergrund_seitenleiste" in profile, f"{name}: Schlüssel fehlt"
