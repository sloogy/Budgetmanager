#!/usr/bin/env python3
"""Gemeinsamer Designkatalog fuer LifePlanner, BudgetManager, FPM und
FreizeitManager.

Warum es diese Datei gibt: Die vier Programme lieferten bis hierher jeweils
eigene Profildateien aus. BudgetManager und LifePlanner kannten 26 Designs mit
29 Rollen, FPM und FreizeitManager sieben Designs mit 38-40 Rollen - und drei
Designs trugen in beiden Lagern verschiedene Namen. Die Folge war sichtbar:
Wer im LifePlanner "Gruvbox - Hell" waehlte, bekam im Modul zwar den
Gruvbox-Hintergrund, aber Standardblau fuer Akzent, Karten und Statusfarben.
Denn was der Host nicht mitliefert, faellt im Modul auf das eingebaute Profil
zurueck.

Dieses Werkzeug macht aus den vier Bestaenden einen Katalog:

* ``ROLES`` beschreibt jede Rolle einmal - fuer alle Programme zusammen. Ein
  Programm liest daraus, was es kennt, und ueberliest den Rest.
* Fehlende Rollen werden nicht erfunden, sondern aus vorhandenen Farben
  desselben Profils abgeleitet (``DERIVATIONS``). Ein bereits gesetzter Wert
  gewinnt immer - handverlesene Farben bleiben unangetastet.
* Kontraste werden geprueft. Reine Vordergrundrollen (``*_text``) werden
  automatisch nachgezogen, wenn sie auf ihrem Grund nicht lesbar sind.

``build`` schreibt den Katalog in alle Zielverzeichnisse, ``check`` prueft nur
und liefert einen Rueckgabewert - so kann ein Test dieselbe Pruefung fahren.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "shared.design.v2"

# Rollen, die es in der Vorlage gar nicht gab und die das Werkzeug erzeugt
# hat, stehen unter diesem Schluessel. Ohne diese Marke waeren sie beim
# naechsten Lauf von handgewaehlten Farben nicht zu unterscheiden - eine
# verbesserte Ableitungsregel kaeme nie mehr zum Zug, weil "ein gesetzter
# Wert gewinnt immer" gilt.
#
# Nur *erzeugte* Rollen stehen hier, keine nachjustierten: Wer einen Wert
# mitbringt, den das Werkzeug nur um eine Nuance verschoben hat, behaelt
# ihn als Vorlage - die Verschiebung wird beim naechsten Lauf aus dem
# Original neu gerechnet. Sonst waere der Katalog nicht reproduzierbar,
# sondern wanderte mit jedem Lauf ein Stueck weiter.
DERIVED_KEY = "_abgeleitet"

# Ausgangswerte der Rollen, die das Werkzeug nachjustiert hat. Ohne sie
# waere der naechste Lauf nicht reproduzierbar: er wuerde vom bereits
# verschobenen Wert aus weiterschieben, statt die Verschiebung aus dem
# Original neu zu rechnen.
SOURCE_KEY = "_vorlage"

_HEX = re.compile(r"#[0-9a-fA-F]{6}")

# ── Rollen ───────────────────────────────────────────────────────────────────
# Der Kern gilt in allen vier Programmen. Jede Profildatei muss ihn vollstaendig
# fuehren - sonst faellt ein Modul beim Uebernehmen des Hostprofils auf sein
# eingebautes Standarddesign zurueck, und genau das war der Fehler.
CORE_ROLES: tuple[str, ...] = (
    "hintergrund_app", "hintergrund_panel", "hintergrund_seitenleiste",
    "seitenleiste_text", "seitenleiste_text_gedimmt", "seitenleiste_aktiv",
    "text", "text_gedimmt", "text_invers",
    "akzent", "akzent_text", "akzent_hover",
    "rand", "eingabe_hintergrund",
    "tabelle_hintergrund", "tabelle_alt", "tabelle_header", "tabelle_header_text",
    "tabelle_gitter", "auswahl_hintergrund", "auswahl_text",
    "hover_hintergrund", "hover_text",
    "karte_hintergrund", "karte_rand",
    "erfolg", "erfolg_text", "warnung", "warnung_text", "gefahr", "gefahr_text",
    "gedaempft", "gedaempft_text",
)

# Bedeutungsfarben einzelner Programme. Sie stehen mit im Katalog, damit ein
# Wechsel des gemeinsamen Designs auch die fachlichen Farben mitnimmt.
APP_ROLES: dict[str, tuple[str, ...]] = {
    "budgetmanager": (
        "typ_einnahmen", "typ_ausgaben", "typ_ersparnisse", "negativ_text",
        "akzent_panel_text",
        "dropdown_bg", "dropdown_text", "dropdown_selection",
        "dropdown_selection_text", "dropdown_border",
    ),
    "fpm": (
        "bereich_sammlung", "bereich_rotation", "bereich_service",
        "bereich_aktivitaet",
    ),
    "freizeitmanager": (
        "ruhe_hintergrund", "ruhe_rand", "ruhe_text",
        "dringlichkeit_frisch", "dringlichkeit_bald", "dringlichkeit_faellig",
        "dringlichkeit_lange", "dringlichkeit_geplant",
    ),
}

ALL_ROLES: tuple[str, ...] = CORE_ROLES + tuple(
    role for roles in APP_ROLES.values() for role in roles
)

# ── Farbrechnung ─────────────────────────────────────────────────────────────
def _rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(part))):02x}" for part in rgb)


def is_hex_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX.fullmatch(value.strip()))


def luminance(color: str) -> float:
    """Relative Helligkeit nach WCAG 2.1."""
    channels = []
    for part in _rgb(color):
        ratio = part / 255.0
        channels.append(ratio / 12.92 if ratio <= 0.04045
                        else ((ratio + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(front: str, back: str) -> float:
    """Kontrastverhaeltnis 1.0 bis 21.0."""
    first, second = luminance(front), luminance(back)
    if first < second:
        first, second = second, first
    return (first + 0.05) / (second + 0.05)


def mix(first: str, second: str, ratio: float) -> str:
    """``ratio`` Anteile von ``second`` in ``first``."""
    ratio = max(0.0, min(1.0, ratio))
    return _hex(tuple(a + (b - a) * ratio for a, b in zip(_rgb(first), _rgb(second))))


def readable_on(background: str, dark: str = "#111827", light: str = "#ffffff") -> str:
    """Die besser lesbare der beiden Textfarben."""
    return dark if contrast(dark, background) >= contrast(light, background) else light


# Eine gedimmte Schrift, die sich von der normalen nicht unterscheidet, dimmt
# nichts. In "Solarized - Dunkel" waren beide Werte buchstaeblich derselbe -
# jede Nebenangabe stand dort so kraeftig wie der Fliesstext.
DIMMED_MIN_SEPARATION = 1.25


def dimmed(text: str, toward: str, backgrounds: tuple[str, ...],
           target: float = 4.5, separation: float = DIMMED_MIN_SEPARATION) -> str:
    """Die staerkste Abschwaechung, die auf jedem Grund noch lesbar bleibt."""
    best = text
    for step in range(1, 21):
        candidate = mix(text, toward, step * 0.05)
        if any(contrast(candidate, background) < target for background in backgrounds):
            break
        best = candidate
        if contrast(text, candidate) >= separation:
            break
    return best


def toward_contrast(color: str, background: str, target: float,
                    dark_mode: bool) -> str:
    """Hellt oder dunkelt ``color`` ab, bis der Kontrast reicht.

    Im dunklen Profil wird aufgehellt, im hellen abgedunkelt - so bleibt die
    Farbe erkennbar dieselbe, statt in ihr Gegenteil zu kippen.
    """
    if contrast(color, background) >= target:
        return color
    goal = "#ffffff" if dark_mode else "#000000"
    best = color
    for step in range(1, 21):
        candidate = mix(color, goal, step * 0.05)
        best = candidate
        if contrast(candidate, background) >= target:
            return candidate
    # Reicht die eigene Richtung nicht, entscheidet die Lesbarkeit.
    return best if contrast(best, background) >= contrast(readable_on(background), background) \
        else readable_on(background)


# ── Farbfehlsichtigkeit ──────────────────────────────────────────────────────
# Rund acht Prozent der Maenner sehen Rot und Gruen nicht auseinander. Wo eine
# Farbe die einzige Aussage traegt - Ampel, Bereichskachel, Buchungstyp -, ist
# ein Farbpaar, das fuer sie gleich aussieht, schlicht keine Aussage. Die
# Simulation folgt Vienot/Brettel/Mollon (1999) ueber den LMS-Raum.
_TO_LMS = ((0.31399022, 0.63951294, 0.04649755),
           (0.15537241, 0.75789446, 0.08670142),
           (0.01775239, 0.10944209, 0.87256922))
_FROM_LMS = ((5.47221206, -4.6419601, 0.16963708),
             (-1.1252419, 2.29317094, -0.1678952),
             (0.02980165, -0.19318073, 1.16364789))
VISION = {
    "protanopie":   ((0, 1.05118294, -0.05116099), (0, 1, 0), (0, 0, 1)),
    "deuteranopie": ((1, 0, 0), (0.9513092, 0, 0.04866992), (0, 0, 1)),
    "tritanopie":   ((1, 0, 0), (0, 1, 0), (-0.86744736, 1.86727089, 0)),
}

# Ab hier gelten zwei Farben als unterscheidbar. dE 20 ist ein deutlich
# sichtbarer Unterschied; ein Helligkeitsunterschied von 1.35:1 traegt auch
# dann, wenn der Farbton verlorengeht.
CVD_MIN_DELTA_E = 20.0
CVD_MIN_CONTRAST = 1.35

# Gruppen, in denen jede Farbe gegen jede andere stehen muss.
SIGNAL_GROUPS: tuple[tuple[str, ...], ...] = (
    ("erfolg", "warnung", "gefahr"),
    ("typ_einnahmen", "typ_ausgaben", "typ_ersparnisse"),
    ("bereich_sammlung", "bereich_rotation", "bereich_service", "bereich_aktivitaet"),
    ("dringlichkeit_frisch", "dringlichkeit_bald", "dringlichkeit_faellig",
     "dringlichkeit_lange", "dringlichkeit_geplant"),
)


def _apply(matrix: tuple, vector: tuple) -> tuple[float, float, float]:
    return tuple(sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3))


def _linear(value: float) -> float:
    value /= 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _companded(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return (value * 12.92 if value <= 0.0031308
            else 1.055 * value ** (1 / 2.4) - 0.055) * 255


def simulate(color: str, kind: str) -> str:
    """Wie die Farbe mit der genannten Farbfehlsichtigkeit aussieht."""
    linear = tuple(_linear(part) for part in _rgb(color))
    lms = _apply(_TO_LMS, linear)
    return _hex(tuple(_companded(part)
                      for part in _apply(_FROM_LMS, _apply(VISION[kind], lms))))


def _lab(color: str) -> tuple[float, float, float]:
    red, green, blue = (_linear(part) for part in _rgb(color))
    x = (0.4124 * red + 0.3576 * green + 0.1805 * blue) / 0.95047
    y = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    z = (0.0193 * red + 0.1192 * green + 0.9505 * blue) / 1.08883

    def f(value: float) -> float:
        return value ** (1 / 3) if value > 0.008856 else 7.787 * value + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(first: str, second: str) -> float:
    """Wahrgenommener Abstand nach CIE76."""
    a, b = _lab(first), _lab(second)
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def tells_apart(first: str, second: str) -> bool:
    """Bleiben die beiden auch bei jeder Farbfehlsichtigkeit unterscheidbar?"""
    for kind in (None, *VISION):
        a = first if kind is None else simulate(first, kind)
        b = second if kind is None else simulate(second, kind)
        if delta_e(a, b) < CVD_MIN_DELTA_E and contrast(a, b) < CVD_MIN_CONTRAST:
            return False
    return True


def _greyed(color: str) -> str:
    """Grau derselben Helligkeit - das Ziel beim Entsaettigen."""
    target = luminance(color)
    low, high = 0, 255
    for _ in range(12):
        middle = (low + high) // 2
        candidate = _hex((middle, middle, middle))
        if luminance(candidate) < target:
            low = middle
        else:
            high = middle
    return _hex((high, high, high))


def set_apart(color: str, others: tuple[str, ...], card: str,
              dark: bool) -> str:
    """Schiebt ``color`` weg, bis es sich von allen ``others`` abhebt.

    Gesucht wird in zwei Richtungen zugleich: heller/dunkler und blasser.
    Helligkeit bleibt bei jeder Farbfehlsichtigkeit erhalten, Saettigung nicht -
    manchmal braucht es beides. In "Monokai - Dunkel" ist der Akzent dieselbe
    Farbe wie "Erfolg"; dort traegt nur "dunkler und blasser".

    Die kleinste ausreichende Aenderung gewinnt, damit das Design so nah wie
    moeglich an seiner Vorlage bleibt.
    """
    if all(tells_apart(color, other) for other in others):
        return color

    grey = _greyed(color)
    candidates: list[tuple[float, str]] = []
    for fade in (0.0, 0.3, 0.6, 0.85):
        base = mix(color, grey, fade) if fade else color
        for step in range(1, 19):
            for goal in ("#000000", "#ffffff"):
                shift = step * 0.05
                candidates.append((fade + shift, mix(base, goal, shift)))
        if fade:
            candidates.append((fade, base))
    candidates.sort(key=lambda entry: entry[0])

    for _, candidate in candidates:
        if contrast(candidate, card) < SIGNAL_MIN_CONTRAST:
            continue
        # Auf der Flaeche steht spaeter Schrift. Ein Ton, der keine lesbare
        # Schrift traegt, ist als Ausweichfarbe unbrauchbar.
        if contrast(readable_on(candidate), candidate) < 4.5:
            continue
        if all(tells_apart(candidate, other) for other in others):
            return candidate
    return color


# ── Ableitungen ──────────────────────────────────────────────────────────────
# Reihenfolge zaehlt: spaetere Regeln duerfen auf frueher abgeleitete Rollen
# zugreifen. Jede Regel bekommt das Profil und liefert eine Farbe.
def _dark(profile: dict[str, Any]) -> bool:
    return str(profile.get("modus", "hell")).strip().lower() == "dunkel"


def _get(profile: dict[str, Any], key: str, fallback: str = "#808080") -> str:
    value = profile.get(key)
    return str(value).strip() if is_hex_color(value) else fallback


# Bedeutungsfarben haben eine feste Aussage - Gruen heisst gut, Rot heisst
# Achtung. Sie werden nur leicht in Richtung Akzent gemischt, damit sie im
# Profil sitzen, ohne ihre Aussage zu verlieren.
_MEANING = {
    "hell": {"erfolg": "#27ae60", "warnung": "#f39c12", "gefahr": "#e74c3c",
             "sammlung": "#8e44ad", "rotation": "#d35400", "service": "#c0392b",
             "aktivitaet": "#2563eb"},
    "dunkel": {"erfolg": "#22c55e", "warnung": "#eab308", "gefahr": "#ef4444",
               "sammlung": "#c084fc", "rotation": "#fb923c", "service": "#f87171",
               "aktivitaet": "#60a5fa"},
}


def _meaning(profile: dict[str, Any], key: str, blend: float = 0.16) -> str:
    base = _MEANING["dunkel" if _dark(profile) else "hell"][key]
    return mix(base, _get(profile, "akzent", base), blend)


DERIVATIONS: tuple[tuple[str, Any], ...] = (
    # Grundflaechen
    ("hintergrund_panel", lambda p: _get(p, "hintergrund_app")),
    ("hintergrund_seitenleiste", lambda p: _get(p, "hintergrund_panel")),
    ("rand", lambda p: p.get("tabelle_gitter") if is_hex_color(p.get("tabelle_gitter"))
     else mix(_get(p, "hintergrund_panel"), "#ffffff" if _dark(p) else "#000000", 0.18)),
    ("eingabe_hintergrund", lambda p: _get(p, "hintergrund_panel")),
    ("karte_hintergrund", lambda p: _get(p, "hintergrund_panel")),
    ("karte_rand", lambda p: _get(p, "rand")),
    # Schrift
    ("text_gedimmt", lambda p: mix(_get(p, "text"), _get(p, "hintergrund_panel"), 0.38)),
    ("text_invers", lambda p: readable_on(_get(p, "text"))),
    # Akzent
    ("akzent_text", lambda p: readable_on(_get(p, "akzent"))),
    ("akzent_hover", lambda p: mix(_get(p, "akzent"),
                                   "#ffffff" if _dark(p) else "#000000", 0.18)),
    # Seitenleiste - sie hat oft einen eigenen, dunkleren Grund als der Rest.
    ("seitenleiste_text", lambda p: _get(p, "text")
     if contrast(_get(p, "text"), _get(p, "hintergrund_seitenleiste")) >= 4.5
     else readable_on(_get(p, "hintergrund_seitenleiste"))),
    ("seitenleiste_text_gedimmt", lambda p: mix(_get(p, "seitenleiste_text"),
                                                _get(p, "hintergrund_seitenleiste"), 0.38)),
    ("seitenleiste_aktiv", lambda p: _get(p, "akzent")),
    # Tabellen
    ("tabelle_hintergrund", lambda p: _get(p, "hintergrund_panel")),
    ("tabelle_alt", lambda p: mix(_get(p, "tabelle_hintergrund"),
                                  "#ffffff" if _dark(p) else "#000000", 0.05)),
    ("tabelle_header", lambda p: mix(_get(p, "tabelle_hintergrund"),
                                     "#ffffff" if _dark(p) else "#000000", 0.08)),
    ("tabelle_header_text", lambda p: _get(p, "text_gedimmt")),
    ("tabelle_gitter", lambda p: _get(p, "rand")),
    ("auswahl_hintergrund", lambda p: _get(p, "akzent")),
    ("auswahl_text", lambda p: readable_on(_get(p, "auswahl_hintergrund"))),
    ("hover_hintergrund", lambda p: mix(_get(p, "hintergrund_panel"),
                                        _get(p, "akzent"), 0.14)),
    ("hover_text", lambda p: _get(p, "text")),
    # Bedeutungsfarben. Der BudgetManager fuehrt seine Typfarben laenger als
    # es die Statusrollen gibt - wo sie da sind, sind sie die bessere Quelle.
    ("erfolg", lambda p: p.get("typ_einnahmen") if is_hex_color(p.get("typ_einnahmen"))
     else _meaning(p, "erfolg")),
    ("gefahr", lambda p: p.get("typ_ausgaben") if is_hex_color(p.get("typ_ausgaben"))
     else _meaning(p, "gefahr")),
    ("warnung", lambda p: _meaning(p, "warnung")),
    ("erfolg_text", lambda p: readable_on(_get(p, "erfolg"))),
    ("warnung_text", lambda p: readable_on(_get(p, "warnung"))),
    ("gefahr_text", lambda p: readable_on(_get(p, "gefahr"))),
    ("gedaempft", lambda p: _get(p, "text_gedimmt")),
    ("gedaempft_text", lambda p: readable_on(_get(p, "gedaempft"))),
    # BudgetManager
    ("typ_einnahmen", lambda p: _get(p, "erfolg")),
    ("typ_ausgaben", lambda p: _get(p, "gefahr")),
    ("typ_ersparnisse", lambda p: _get(p, "akzent")),
    ("negativ_text", lambda p: toward_contrast(_get(p, "gefahr"),
                                               _get(p, "hintergrund_panel"), 4.5, _dark(p))),
    ("akzent_panel_text", lambda p: toward_contrast(_get(p, "akzent"),
                                                    _get(p, "hintergrund_panel"), 4.5, _dark(p))),
    ("dropdown_bg", lambda p: _get(p, "eingabe_hintergrund")),
    ("dropdown_text", lambda p: _get(p, "text")),
    ("dropdown_selection", lambda p: _get(p, "auswahl_hintergrund")),
    ("dropdown_selection_text", lambda p: _get(p, "auswahl_text")),
    ("dropdown_border", lambda p: _get(p, "rand")),
    # FPM - die vier Bereiche des Dashboards muessen untereinander
    # unterscheidbar bleiben, deshalb feste Grundtoene statt Akzentvarianten.
    ("bereich_sammlung", lambda p: _meaning(p, "sammlung")),
    ("bereich_rotation", lambda p: _meaning(p, "rotation")),
    ("bereich_service", lambda p: _meaning(p, "service")),
    ("bereich_aktivitaet", lambda p: _meaning(p, "aktivitaet")),
    # FreizeitManager
    ("dringlichkeit_frisch", lambda p: _get(p, "erfolg")),
    ("dringlichkeit_bald", lambda p: _get(p, "warnung")),
    ("dringlichkeit_faellig", lambda p: mix(_get(p, "warnung"), _get(p, "gefahr"), 0.5)),
    ("dringlichkeit_lange", lambda p: _get(p, "akzent")),
    # "Geplant" ist ein neutraler Zustand, kein Signal. Aus dem Akzent gemischt
    # fiel es in gruenen Designs mit "frisch" zusammen; aus der gedaempften
    # Farbe gemischt bleibt es neutral und hebt sich von beiden ab.
    ("dringlichkeit_geplant", lambda p: mix(_get(p, "gedaempft"), _get(p, "akzent"), 0.25)),
    ("ruhe_hintergrund", lambda p: mix(_get(p, "hintergrund_panel"), _get(p, "erfolg"), 0.22)),
    ("ruhe_rand", lambda p: _get(p, "erfolg")),
    ("ruhe_text", lambda p: toward_contrast(mix(_get(p, "erfolg"), _get(p, "text"), 0.35),
                                            _get(p, "ruhe_hintergrund"), 4.5, _dark(p))),
)

# Wer bei zu wenig Kontrast nachgibt. ``text`` und die beiden Grundflaechen
# sind das Design - sie bleiben. Nachgeben duerfen die Schriftfarbe (wo sie nur
# lesbar sein muss) oder eine abgeleitete Flaeche wie die Seitenleiste.
FRONT, BACK = "vordergrund", "hintergrund"

# Die Schwelle stammt aus dem BudgetManager: 4.5:1 fuer jede Schrift auf jedem
# Grund. Sie ist die strengste der vier Programme - und damit die richtige fuer
# einen gemeinsamen Katalog.
FOREGROUND_PAIRS: tuple[tuple[str, str, float, str], ...] = (
    # Der Fliesstext steht fest; passt es nicht, ist die Flaeche falsch.
    ("text", "hintergrund_app", 4.5, BACK),
    ("text", "hintergrund_panel", 4.5, BACK),
    ("text", "hintergrund_seitenleiste", 4.5, BACK),
    ("text", "tabelle_hintergrund", 4.5, BACK),
    ("text", "tabelle_alt", 4.5, BACK),
    ("text", "karte_hintergrund", 4.5, BACK),
    ("text", "eingabe_hintergrund", 4.5, BACK),
    # Zweitrangige Schriften geben selbst nach.
    ("text_gedimmt", "hintergrund_app", 4.5, FRONT),
    ("text_gedimmt", "hintergrund_panel", 4.5, FRONT),
    ("text_gedimmt", "hintergrund_seitenleiste", 4.5, FRONT),
    ("text_gedimmt", "karte_hintergrund", 4.5, FRONT),
    ("seitenleiste_text", "hintergrund_seitenleiste", 4.5, FRONT),
    ("seitenleiste_text_gedimmt", "hintergrund_seitenleiste", 4.5, FRONT),
    ("tabelle_header_text", "tabelle_header", 4.5, FRONT),
    ("akzent_text", "akzent", 4.5, FRONT),
    ("akzent_panel_text", "hintergrund_panel", 4.5, FRONT),
    ("auswahl_text", "auswahl_hintergrund", 4.5, FRONT),
    ("hover_text", "hover_hintergrund", 4.5, FRONT),
    ("erfolg_text", "erfolg", 4.5, FRONT),
    ("warnung_text", "warnung", 4.5, FRONT),
    ("gefahr_text", "gefahr", 4.5, FRONT),
    ("gedaempft_text", "gedaempft", 4.5, FRONT),
    ("dropdown_text", "dropdown_bg", 4.5, FRONT),
    ("dropdown_selection_text", "dropdown_selection", 4.5, FRONT),
    ("negativ_text", "hintergrund_app", 4.5, FRONT),
    ("negativ_text", "hintergrund_panel", 4.5, FRONT),
    ("negativ_text", "tabelle_hintergrund", 4.5, FRONT),
    ("negativ_text", "tabelle_alt", 4.5, FRONT),
    ("ruhe_text", "ruhe_hintergrund", 4.5, FRONT),
)

# Flaechen, die nachgeben duerfen. App- und Panelhintergrund sind das Design
# selbst - stimmt dort der Kontrast nicht, ist das ein Befund, keine Reparatur.
ADJUSTABLE_SURFACES: frozenset[str] = frozenset({
    "hintergrund_seitenleiste", "tabelle_hintergrund", "tabelle_alt",
    "karte_hintergrund", "eingabe_hintergrund", "tabelle_header",
    "hover_hintergrund",
})

# Farben, die eine Aussage tragen und deshalb auf der Karte erkennbar sein
# muessen. Ein abgeleitetes Gelb auf hellem Grund erreichte hier 1.77:1 - das
# ist als Ampelfarbe wertlos. 2.6:1 laesst noch Luft ueber der Untergrenze der
# Programme (2.0:1), ohne die Farbe zu verfaelschen.
SIGNAL_ROLES: tuple[str, ...] = (
    "akzent", "erfolg", "warnung", "gefahr", "gedaempft",
    "typ_einnahmen", "typ_ausgaben", "typ_ersparnisse",
    "bereich_sammlung", "bereich_rotation", "bereich_service", "bereich_aktivitaet",
    "dringlichkeit_frisch", "dringlichkeit_bald", "dringlichkeit_faellig",
    "dringlichkeit_lange", "dringlichkeit_geplant",
)
SIGNAL_BACKGROUND = "karte_hintergrund"
SIGNAL_MIN_CONTRAST = 2.6


# Reicht keine Schriftfarbe, darf die Bedeutungsflaeche selbst nachgeben.
# Der Nord-Rotton traegt zum Beispiel weder weisse noch schwarze Schrift mit
# 4.5:1; eine Nuance dunkler faellt niemandem auf, unlesbare Schrift schon.
ADJUSTABLE_BACKGROUNDS: frozenset[str] = frozenset({
    "akzent", "auswahl_hintergrund", "hover_hintergrund", "tabelle_header",
    "erfolg", "warnung", "gefahr", "gedaempft",
    "dropdown_selection", "ruhe_hintergrund",
})


def away_from(background: str, front: str, target: float) -> str:
    """Schiebt den Grund von der Schrift weg, bis der Kontrast reicht."""
    goal = "#000000" if luminance(front) > luminance(background) else "#ffffff"
    for step in range(1, 21):
        candidate = mix(background, goal, step * 0.04)
        if contrast(front, candidate) >= target:
            return candidate
    return mix(background, goal, 0.8)


# ── Katalog ──────────────────────────────────────────────────────────────────
# Dieselben Designs hiessen in beiden Lagern verschieden. Wer im LifePlanner
# "Kontrast - Schwarz/Weiss" waehlte, suchte das Modul unter diesem Namen
# vergeblich, obwohl es dasselbe Design als "Kontrast Schwarzweiss" mitbrachte.
# Der linke Name ist ab jetzt der gueltige.
CANONICAL_NAMES: dict[str, str] = {
    "Standard Hell": "Standard - Hell",
    "Standard Dunkel": "Standard - Dunkel",
    "Kontrast Schwarzweiss": "Kontrast - Schwarz/Weiß",
    "Warm Sepia - Hell": "Hell - Warm (Sepia)",
    "OLED Schwarz": "Dunkel - OLED (Kontrastarm)",
}

# Einheitliche Schriftgroesse. Die Module rechnen sie in ihren eigenen
# Massstab um; 10 ist der gemeinsame Bezugswert.
DEFAULT_FONT_SIZE = 10
FONT_SIZE_MIN, FONT_SIZE_MAX = 8, 22

# Repo-Ordner -> Profilverzeichnis. Der Katalog liegt in jedem Programm, damit
# jedes fuer sich lauffaehig bleibt; identisch gehalten wird er hierueber.
TARGETS: dict[str, tuple[str, str]] = {
    "lifeplanner": ("Liveplanner", "lifeplanner_core/themes"),
    "budgetmanager": ("Budgetmanager", "views/profiles"),
    "fpm": ("FPM", "ui/profiles"),
    "freizeitmanager": ("Kontaktmanager", "freizeitmanager/ui/profiles"),
}


def local_profile_dir() -> Path | None:
    """Das Profilverzeichnis des Programms, in dem diese Datei liegt.

    Der Katalog liegt in jedem der vier Programme als dieselbe Datei. Damit sie
    das auch bleiben kann, wird das eigene Verzeichnis gesucht statt eingetragen.
    """
    repo = Path(__file__).resolve().parents[1]
    for _, relative in TARGETS.values():
        candidate = repo / relative
        if candidate.is_dir():
            return candidate
    return None


def slugify(name: str) -> str:
    text = str(name or "").strip().lower()
    for source, target in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
                           ("–", "-"), ("—", "-")):
        text = text.replace(source, target)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_\-]", "", text).replace("-", "_")
    return re.sub(r"_+", "_", text).strip("_") or "profil"


def canonical_name(name: str) -> str:
    return CANONICAL_NAMES.get(str(name or "").strip(), str(name or "").strip())


def _repair_foregrounds(result: dict[str, Any], touched: list[str], *,
                        passes: int, move_surfaces: bool) -> None:
    """Zieht Schriftfarben nach, bis sie auf ihrem Grund lesbar sind.

    ``move_surfaces`` entscheidet, ob dabei auch die Flaeche nachgeben darf.
    Nach der Trennung der Bedeutungsfarben muss sie das nicht mehr - sonst
    wuerde sie den eben gewonnenen Abstand wieder einebnen.
    """
    for _ in range(passes):
        for role, background, target, gives_way in FOREGROUND_PAIRS:
            if not (is_hex_color(result.get(role)) and is_hex_color(result.get(background))):
                continue
            if contrast(result[role], result[background]) >= target - 0.005:
                continue
            if gives_way == BACK and background in ADJUSTABLE_SURFACES:
                if not move_surfaces:
                    continue
                result[background] = away_from(result[background], result[role], target)
                if background not in touched:
                    touched.append(background)
                continue
            fixed = toward_contrast(result[role], result[background], target, _dark(result))
            if fixed != result[role]:
                result[role] = fixed
                if role not in touched:
                    touched.append(role)
            if (contrast(result[role], result[background]) < target - 0.005
                    and move_surfaces and background in ADJUSTABLE_BACKGROUNDS):
                result[background] = away_from(result[background], result[role], target)
                if background not in touched:
                    touched.append(background)


def complete(profile: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Ergaenzt fehlende Rollen und zieht unlesbare Vordergruende nach.

    Liefert das vollstaendige Profil und die Liste der Rollen, die nicht aus
    der Vorlage stammen - damit ``build`` berichten kann, was es getan hat.
    """
    result = dict(profile)
    result.pop(DERIVED_KEY, None)
    result.pop(SOURCE_KEY, None)
    touched: list[str] = []
    created: list[str] = []

    for role, rule in DERIVATIONS:
        if is_hex_color(result.get(role)):
            continue
        result[role] = rule(result)
        touched.append(role)
        created.append(role)

    # Die Seitenleiste gehoert zur Helligkeit des Profils. Eine dunkle Leiste
    # im hellen Design war im BudgetManager ein gemeldeter Fehler - FPM und der
    # FreizeitManager brachten aber genau das mit. Der Katalog folgt der Regel
    # des BudgetManagers, weil dort die Schrift der Leiste aus ``text`` kommt.
    side = result.get("hintergrund_seitenleiste")
    if is_hex_color(side) and _dark(result) != (luminance(side) < 0.5):
        base = _get(result, "hintergrund_app")
        result["hintergrund_seitenleiste"] = mix(
            base, "#000000", 0.35 if _dark(result) else 0.06)
        if "hintergrund_seitenleiste" not in touched:
            touched.append("hintergrund_seitenleiste")

    # Die Schrift der Leiste stammt in mehreren Profilen aus einer anderen,
    # gegenteilig hellen Leiste - in "Solarized - Hell" war sie sogar exakt die
    # Farbe der Leiste selbst. Ein Wert, der auf seinem Grund nicht lesbar ist,
    # wird verworfen und neu abgeleitet, statt ihn muehsam zurechtzuruecken.
    side = _get(result, "hintergrund_seitenleiste")
    for role in ("seitenleiste_text", "seitenleiste_text_gedimmt"):
        value = result.get(role)
        if is_hex_color(value) and contrast(value, side) >= 4.5:
            continue
        result.pop(role, None)
        if role not in touched:
            touched.append(role)
    for role, rule in DERIVATIONS:
        if role.startswith("seitenleiste_") and not is_hex_color(result.get(role)):
            result[role] = rule(result)
            if role not in created:
                created.append(role)

    # Gedimmte Schrift muss sich von der normalen abheben - und trotzdem auf
    # jedem Grund lesbar bleiben. Reicht der Spielraum nicht, bekommt der
    # Fliesstext etwas mehr Kontrast; das ist nie ein Nachteil.
    for strong, weak, grounds in (
        ("text", "text_gedimmt",
         ("hintergrund_app", "hintergrund_panel", "hintergrund_seitenleiste",
          "karte_hintergrund")),
        ("seitenleiste_text", "seitenleiste_text_gedimmt",
         ("hintergrund_seitenleiste",)),
    ):
        grounds = tuple(result[g] for g in grounds if is_hex_color(result.get(g)))
        if not (is_hex_color(result.get(strong)) and is_hex_color(result.get(weak)) and grounds):
            continue
        toward = _get(result, "hintergrund_panel" if strong == "text"
                      else "hintergrund_seitenleiste")
        for _ in range(4):
            candidate = dimmed(result[strong], toward, grounds)
            if contrast(result[strong], candidate) >= DIMMED_MIN_SEPARATION:
                break
            result[strong] = mix(result[strong], "#ffffff" if _dark(result) else "#000000", 0.12)
            if strong not in touched:
                touched.append(strong)
        if candidate != result[weak]:
            result[weak] = candidate
            if weak not in touched:
                touched.append(weak)
    if "text" in touched:
        result["text_invers"] = readable_on(result["text"])

    card = result.get(SIGNAL_BACKGROUND)
    if is_hex_color(card):
        for role in SIGNAL_ROLES:
            if not is_hex_color(result.get(role)):
                continue
            fixed = toward_contrast(result[role], card, SIGNAL_MIN_CONTRAST, _dark(result))
            if fixed != result[role]:
                result[role] = fixed
                if role not in touched:
                    touched.append(role)

    _repair_foregrounds(result, touched, passes=2, move_surfaces=True)

    if is_hex_color(card):
        for group in SIGNAL_GROUPS:
            present = [role for role in group if is_hex_color(result.get(role))]
            for index, role in enumerate(present[1:], start=1):
                others = tuple(result[earlier] for earlier in present[:index])
                fixed = set_apart(result[role], others, card, _dark(result))
                if fixed != result[role]:
                    result[role] = fixed
                    if role not in touched:
                        touched.append(role)
                    continue
                if all(tells_apart(result[role], other) for other in others):
                    continue
                # Die spaetere Farbe kann nicht ausweichen - dann muss die
                # fruehere. Rot und Gruen liegen bei Rotgruenblindheit so nah
                # beieinander, dass nur ein Helligkeitsabstand hilft, und der
                # geht manchmal nur nach der anderen Seite.
                for earlier in present[:index]:
                    rest = tuple(result[other] for other in present[:index]
                                 if other != earlier) + (result[role],)
                    moved = set_apart(result[earlier], rest, card, _dark(result))
                    if moved != result[earlier]:
                        result[earlier] = moved
                        if earlier not in touched:
                            touched.append(earlier)
                        break


    # Die Bedeutungsfarben haben sich eben verschoben - die Schrift darauf muss
    # nachziehen. Diesmal ohne Flaechen zu bewegen, sonst waere der eben
    # gewonnene Abstand wieder dahin.
    _repair_foregrounds(result, touched, passes=1, move_surfaces=False)

    result["schriftgroesse"] = DEFAULT_FONT_SIZE
    result[DERIVED_KEY] = sorted(created)
    result[SOURCE_KEY] = {role: profile[role] for role in sorted(touched)
                          if role not in created and is_hex_color(profile.get(role))}
    return result, touched


def audit(profile: dict[str, Any]) -> list[str]:
    """Was an einem Profil noch nicht stimmt - leer heisst in Ordnung."""
    problems: list[str] = []
    name = profile.get("name", "?")

    if str(profile.get("modus", "")).strip().lower() not in ("hell", "dunkel"):
        problems.append(f"{name}: modus fehlt oder ist ungueltig")

    size = profile.get("schriftgroesse")
    if not isinstance(size, int) or not FONT_SIZE_MIN <= size <= FONT_SIZE_MAX:
        problems.append(f"{name}: schriftgroesse {size!r} liegt ausserhalb "
                        f"{FONT_SIZE_MIN}-{FONT_SIZE_MAX}")

    marked = profile.get(DERIVED_KEY)
    if marked is not None and not isinstance(marked, list):
        problems.append(f"{name}: {DERIVED_KEY} ist keine Liste")
    origin = profile.get(SOURCE_KEY)
    if origin is not None and not isinstance(origin, dict):
        problems.append(f"{name}: {SOURCE_KEY} ist kein Objekt")

    for role in ALL_ROLES:
        if not is_hex_color(profile.get(role)):
            problems.append(f"{name}: Rolle {role} fehlt")

    card = profile.get(SIGNAL_BACKGROUND)
    if is_hex_color(card):
        for role in SIGNAL_ROLES:
            if not is_hex_color(profile.get(role)):
                continue
            ratio = contrast(profile[role], card)
            if ratio < SIGNAL_MIN_CONTRAST - 0.05:
                problems.append(f"{name}: {role} hebt sich mit {ratio:.2f}:1 zu wenig "
                                f"von der Karte ab (noetig {SIGNAL_MIN_CONTRAST}:1)")

    side = profile.get("hintergrund_seitenleiste")
    if is_hex_color(side) and _dark(profile) != (luminance(side) < 0.5):
        helligkeit = "dunkles" if _dark(profile) else "helles"
        problems.append(f"{name}: {helligkeit} Profil, aber Seitenleiste {side}")

    for group in SIGNAL_GROUPS:
        present = [role for role in group if is_hex_color(profile.get(role))]
        for index, role in enumerate(present):
            for other in present[index + 1:]:
                if not tells_apart(profile[role], profile[other]):
                    problems.append(f"{name}: {role} und {other} sind bei "
                                    f"Farbfehlsichtigkeit nicht zu unterscheiden")

    for strong, weak in (("text", "text_gedimmt"),
                         ("seitenleiste_text", "seitenleiste_text_gedimmt")):
        if not (is_hex_color(profile.get(strong)) and is_hex_color(profile.get(weak))):
            continue
        ratio = contrast(profile[strong], profile[weak])
        if ratio < DIMMED_MIN_SEPARATION - 0.02:
            problems.append(f"{name}: {weak} unterscheidet sich mit {ratio:.2f}:1 kaum "
                            f"von {strong} (noetig {DIMMED_MIN_SEPARATION}:1)")

    for role, background, target, _gives_way in FOREGROUND_PAIRS:
        if not (is_hex_color(profile.get(role)) and is_hex_color(profile.get(background))):
            continue
        ratio = contrast(profile[role], profile[background])
        if ratio < target - 0.05:
            problems.append(f"{name}: {role} auf {background} nur {ratio:.2f}:1 "
                            f"(noetig {target}:1)")
    return problems


def read_profiles(directory: Path) -> dict[str, dict[str, Any]]:
    """Profile eines Verzeichnisses, nach kanonischem Namen."""
    found: dict[str, dict[str, Any]] = {}
    for file in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  uebersprungen: {file.name} ({exc})", file=sys.stderr)
            continue
        if not isinstance(raw, dict):
            continue
        name = canonical_name(raw.get("name") or file.stem.replace("_", " "))
        raw["name"] = name
        found[name] = raw
    return found


def harvest(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Sammelt den Bestand aller Programme zu einem Katalog.

    Reihenfolge der Quellen zaehlt: Wer eine Rolle bereits mit einer von Hand
    gewaehlten Farbe fuehrt, gewinnt - und zwar der Host zuerst. Er verteilt das
    gemeinsame Design an alle Module, seine 26 Profile sind die aeltesten und am
    laengsten in Gebrauch. Die Module ergaenzen nur, was er nicht fuehrt: den
    neueren, breiteren Rollensatz.

    Das faellt bei den drei umbenannten Designs ins Gewicht. "OLED Schwarz" der
    Module und "Dunkel - OLED (Kontrastarm)" des Hosts sind zwei verschiedene
    Paletten unter einem Namen - waeren die Module zuerst dran, wuerde der
    Akzent des Hosts von Cyan auf Blau springen.
    """
    catalog: dict[str, dict[str, Any]] = {}
    order = ("lifeplanner", "budgetmanager", "fpm", "freizeitmanager")
    for key in order:
        repo, relative = TARGETS[key]
        directory = repo_root / repo / relative
        if not directory.is_dir():
            print(f"  fehlt: {directory}", file=sys.stderr)
            continue
        for name, profile in read_profiles(directory).items():
            target = catalog.setdefault(name, {"name": name})
            derived = set(profile.get(DERIVED_KEY) or ())
            original = profile.get(SOURCE_KEY) or {}
            for role, value in profile.items():
                if role == "name" or role in derived or role.startswith("_"):
                    continue
                value = original.get(role, value)
                if role == "modus":
                    target.setdefault("modus", str(value).strip().lower())
                elif is_hex_color(value) and not is_hex_color(target.get(role)):
                    target[role] = str(value).strip()
    return catalog


def serialise(profile: dict[str, Any]) -> str:
    """Feste Reihenfolge, damit ein Diff nur echte Aenderungen zeigt."""
    ordered: dict[str, Any] = {
        "_schema": SCHEMA,
        "name": profile["name"],
        "modus": profile.get("modus", "hell"),
        "schriftgroesse": profile.get("schriftgroesse", DEFAULT_FONT_SIZE),
    }
    for role in ALL_ROLES:
        if role in profile:
            ordered[role] = profile[role]
    for role in sorted(set(profile) - set(ordered)):
        if role in (DERIVED_KEY, SOURCE_KEY):
            continue
        ordered[role] = profile[role]
    derived = profile.get(DERIVED_KEY)
    if derived:
        ordered[DERIVED_KEY] = sorted(derived)
    source = profile.get(SOURCE_KEY)
    if source:
        ordered[SOURCE_KEY] = {role: source[role] for role in sorted(source)}
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def write_catalog(catalog: dict[str, dict[str, Any]], directory: Path,
                  prune: bool = True) -> tuple[int, int, list[str]]:
    """Schreibt den Katalog. Liefert (geschrieben, entfernt, unveraendert)."""
    directory.mkdir(parents=True, exist_ok=True)
    wanted = {f"{slugify(name)}.json": serialise(profile)
              for name, profile in catalog.items()}

    written, unchanged = 0, []
    for filename, payload in sorted(wanted.items()):
        path = directory / filename
        if path.exists() and path.read_text(encoding="utf-8") == payload:
            unchanged.append(filename)
            continue
        path.write_text(payload, encoding="utf-8")
        written += 1

    removed = 0
    if prune:
        for path in sorted(directory.glob("*.json")):
            if path.name not in wanted:
                path.unlink()
                removed += 1
    return written, removed, unchanged


def build(repo_root: Path, only: Iterable[str] | None = None) -> int:
    catalog = harvest(repo_root)
    if not catalog:
        print("Kein Profil gefunden - stimmt der Pfad?", file=sys.stderr)
        return 2

    problems: list[str] = []
    for name in sorted(catalog):
        catalog[name], touched = complete(catalog[name])
        problems.extend(audit(catalog[name]))
        if touched:
            print(f"  {name}: {len(touched)} Rollen ergaenzt")

    print(f"\nKatalog: {len(catalog)} Designs, {len(ALL_ROLES)} Rollen je Design")
    if problems:
        print("\nNoch offen:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    keys = list(only) if only else list(TARGETS)
    for key in keys:
        repo, relative = TARGETS[key]
        directory = repo_root / repo / relative
        if not directory.parent.is_dir():
            print(f"  uebersprungen: {directory} (Programm nicht vorhanden)")
            continue
        written, removed, unchanged = write_catalog(catalog, directory)
        print(f"  {key:16s} {written:2d} neu/geaendert, {removed:2d} entfernt, "
              f"{len(unchanged):2d} unveraendert -> {relative}")
    return 0


def check(directory: Path) -> int:
    """Prueft ein einzelnes Profilverzeichnis - fuer Tests und CI."""
    profiles = read_profiles(directory)
    problems: list[str] = []

    expected = set(CANONICAL_NAMES.values())
    missing = expected - set(profiles)
    if missing:
        problems.append("Umbenannte Designs fehlen: " + ", ".join(sorted(missing)))

    for name in sorted(profiles):
        problems.extend(audit(profiles[name]))
        slug = slugify(name)
        if not (directory / f"{slug}.json").exists():
            problems.append(f"{name}: Datei heisst nicht {slug}.json")

    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{len(profiles)} Designs geprueft, {len(problems)} Beanstandungen")
    return 1 if problems else 0


# ── Neues Design ─────────────────────────────────────────────────────────────
def make_profile(name: str, mode: str, akzent: str,
                 grund: str | None = None) -> dict[str, Any]:
    """Baut aus Name, Helligkeit und Akzentfarbe ein vollstaendiges Design.

    Die uebrigen 50 Rollen entstehen ueber dieselben Ableitungen und
    Kontrastregeln wie beim Katalog - ein so erzeugtes Design erfuellt also von
    Anfang an, was ``check`` verlangt. Wer mehr Kontrolle will, aendert danach
    einzelne Werte und laesst ``build`` den Rest nachziehen.
    """
    mode = "dunkel" if str(mode).strip().lower().startswith("d") else "hell"
    dark = mode == "dunkel"
    if grund is None:
        # Ein Hauch Akzent im Grund traegt das Design bis in die Flaechen,
        # ohne dass die Oberflaeche bunt wird.
        grund = mix("#101418" if dark else "#ffffff", akzent, 0.06)
    profile: dict[str, Any] = {
        "name": name,
        "modus": mode,
        "hintergrund_app": grund,
        "hintergrund_panel": mix(grund, "#ffffff" if dark else "#000000", 0.05),
        "text": readable_on(grund, dark="#12161c", light="#f5f7fa") if dark
        else readable_on(grund),
        "akzent": akzent,
    }
    profile, _ = complete(profile)
    return profile


def create(name: str, mode: str, akzent: str, grund: str | None,
           repo_root: Path, only: Iterable[str] | None = None) -> int:
    if not is_hex_color(akzent):
        print(f"Akzent {akzent!r} ist keine Farbe wie #2563eb", file=sys.stderr)
        return 2
    if grund is not None and not is_hex_color(grund):
        print(f"Grundfarbe {grund!r} ist keine Farbe wie #ffffff", file=sys.stderr)
        return 2

    profile = make_profile(name, mode, akzent, grund)
    problems = audit(profile)
    if problems:
        print("Das Design erfuellt die Regeln nicht:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    payload = serialise(profile)
    filename = f"{slugify(profile['name'])}.json"
    for key in (list(only) if only else list(TARGETS)):
        repo, relative = TARGETS[key]
        directory = repo_root / repo / relative
        if not directory.is_dir():
            print(f"  uebersprungen: {directory}")
            continue
        (directory / filename).write_text(payload, encoding="utf-8")
        print(f"  {key:16s} -> {relative}/{filename}")
    print(f"\n{profile['name']}: {len(ALL_ROLES)} Rollen, alle Regeln erfuellt.")
    return 0


# ── Vorschau ─────────────────────────────────────────────────────────────────
# Die Rollen, die eine Kachel zeigt: erst die Flaechen, dann Schrift auf Grund,
# dann die Bedeutungsfarben. Farbwerte allein sagen niemandem, wie ein Design
# wirkt - deshalb gibt es diese Seite.
PREVIEW_SWATCHES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Flächen", ("hintergrund_app", "hintergrund_panel", "karte_hintergrund",
                 "hintergrund_seitenleiste", "eingabe_hintergrund", "rand")),
    ("Schrift", ("text", "text_gedimmt", "seitenleiste_text", "text_invers")),
    ("Bedienung", ("akzent", "akzent_hover", "auswahl_hintergrund",
                   "hover_hintergrund", "seitenleiste_aktiv")),
    ("Tabelle", ("tabelle_hintergrund", "tabelle_alt", "tabelle_header",
                 "tabelle_gitter")),
    ("Bedeutung", ("erfolg", "warnung", "gefahr", "gedaempft")),
    ("BudgetManager", ("typ_einnahmen", "typ_ausgaben", "typ_ersparnisse")),
    ("FountainPen Manager", ("bereich_sammlung", "bereich_rotation",
                             "bereich_service", "bereich_aktivitaet")),
    ("FreizeitManager", ("dringlichkeit_frisch", "dringlichkeit_bald",
                         "dringlichkeit_faellig", "dringlichkeit_lange",
                         "dringlichkeit_geplant")),
)


def _preview_card(profile: dict[str, Any]) -> str:
    name = profile["name"]
    get = lambda role: profile.get(role, "#808080")  # noqa: E731
    groups = []
    for label, roles in PREVIEW_SWATCHES:
        chips = "".join(
            f'<div class="chip"><span class="dot" style="background:{get(role)};'
            f'border-color:{get("rand")}"></span>'
            f'<span class="role">{role}</span>'
            f'<span class="hex">{get(role)}</span></div>'
            for role in roles if role in profile)
        groups.append(f'<div class="group"><h4>{label}</h4><div class="chips">{chips}</div></div>')

    # Wie ein Farbfehlsichtiger die Signalfarben sieht. Erst hier wird
    # nachvollziehbar, warum manche Toene im Katalog anders sitzen als in der
    # Vorlage - sie mussten auseinanderruecken.
    signal_roles = tuple(role for role in ("erfolg", "warnung", "gefahr")
                         if role in profile)
    rows = []
    for kind in ("normal", *VISION):
        cells = "".join(
            f'<span style="background:'
            f'{get(role) if kind == "normal" else simulate(get(role), kind)}"></span>'
            for role in signal_roles)
        rows.append(f'<div class="visrow"><span class="vislabel">{kind}</span>'
                    f'<span class="viscells">{cells}</span></div>')
    vision = f'<div class="vision">{"".join(rows)}</div>' if signal_roles else ""

    worst_role, worst = "", 99.0
    for role, background, target, _policy in FOREGROUND_PAIRS:
        if role in profile and background in profile:
            ratio = contrast(profile[role], profile[background])
            if ratio < worst:
                worst, worst_role = ratio, f"{role} auf {background}"

    return f"""<section class="design" style="
      --app:{get('hintergrund_app')};--panel:{get('hintergrund_panel')};
      --karte:{get('karte_hintergrund')};--rand:{get('rand')};
      --text:{get('text')};--dim:{get('text_gedimmt')};
      --akzent:{get('akzent')};--akzent-text:{get('akzent_text')};
      --leiste:{get('hintergrund_seitenleiste')};--leiste-text:{get('seitenleiste_text')}">
  <header>
    <h3>{name}</h3>
    <span class="modus">{profile.get('modus', 'hell')}</span>
  </header>
  <div class="mock">
    <div class="rail">Menü</div>
    <div class="body">
      <div class="card">
        <strong>Karte</strong>
        <p>Fließtext auf der Karte.</p>
        <p class="dim">Nebenangabe, gedimmt.</p>
        <button>Aktion</button>
      </div>
      <div class="signals">
        <span style="background:{get('erfolg')};color:{get('erfolg_text')}">Erfolg</span>
        <span style="background:{get('warnung')};color:{get('warnung_text')}">Warnung</span>
        <span style="background:{get('gefahr')};color:{get('gefahr_text')}">Gefahr</span>
      </div>
    </div>
  </div>
  {vision}
  <div class="groups">{''.join(groups)}</div>
  <footer>schwächster Kontrast: <strong>{worst:.2f}:1</strong> &middot; {worst_role}</footer>
</section>"""


PREVIEW_CSS = """
:root{color-scheme:light dark;--seite:#f6f7f9;--seite-text:#111827;--seite-rand:#d9dee5}
@media (prefers-color-scheme:dark){:root{--seite:#0f172a;--seite-text:#e2e8f0;--seite-rand:#334155}}
*{box-sizing:border-box}
body{margin:0;padding:32px;background:var(--seite);color:var(--seite-text);
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
h1{margin:0 0 4px;font-size:26px}
.lead{margin:0 0 28px;opacity:.75;max-width:62ch}
.grid{display:grid;gap:24px;grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}
.design{border:1px solid var(--seite-rand);border-radius:12px;overflow:hidden;background:var(--app)}
.design header{display:flex;align-items:baseline;gap:10px;padding:12px 16px;
  background:var(--panel);border-bottom:1px solid var(--rand)}
.design h3{margin:0;font-size:16px;color:var(--text)}
.modus{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
.mock{display:flex;min-height:150px}
.rail{width:72px;flex:none;background:var(--leiste);color:var(--leiste-text);
  padding:12px 8px;font-size:12px}
.body{flex:1;padding:14px;display:flex;flex-direction:column;gap:10px}
.card{background:var(--karte);border:1px solid var(--rand);border-radius:8px;
  padding:12px;color:var(--text)}
.card p{margin:6px 0}
.card .dim{color:var(--dim);font-size:13px}
.card button{margin-top:8px;background:var(--akzent);color:var(--akzent-text);
  border:0;border-radius:6px;padding:7px 14px;font:inherit;font-weight:600;cursor:default}
.signals{display:flex;gap:8px;flex-wrap:wrap}
.signals span{padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600}
.vision{padding:9px 16px;background:var(--panel);border-top:1px solid var(--rand);
  display:flex;flex-wrap:wrap;gap:10px 18px;color:var(--dim);font-size:11px}
.visrow{display:flex;align-items:center;gap:6px}
.vislabel{min-width:74px}
.viscells{display:flex;gap:3px}
.viscells span{width:20px;height:12px;border-radius:3px;display:block}
.groups{padding:12px 16px;background:var(--panel);border-top:1px solid var(--rand);
  color:var(--text)}
.group{margin-bottom:10px}
.group h4{margin:0 0 5px;font-size:11px;text-transform:uppercase;
  letter-spacing:.07em;color:var(--dim);font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{display:flex;align-items:center;gap:5px;font-size:11px;
  border:1px solid var(--rand);border-radius:5px;padding:2px 6px}
.dot{width:12px;height:12px;border-radius:3px;border:1px solid;flex:none}
.role{opacity:.85}
.hex{font-family:ui-monospace,monospace;opacity:.6}
.design footer{padding:9px 16px;background:var(--panel);border-top:1px solid var(--rand);
  font-size:12px;color:var(--dim)}
"""


def preview(directory: Path, target: Path) -> int:
    """Schreibt eine HTML-Uebersicht aller Designs."""
    profiles = read_profiles(directory)
    if not profiles:
        print(f"Keine Profile in {directory}", file=sys.stderr)
        return 2
    order = sorted(profiles, key=lambda n: (profiles[n].get("modus") != "hell", n.casefold()))
    cards = "\n".join(_preview_card(profiles[name]) for name in order)
    hell = sum(1 for n in profiles if profiles[n].get("modus") == "hell")
    target.write_text(
        f"<title>Designkatalog</title>\n<style>{PREVIEW_CSS}</style>\n"
        f"<h1>Gemeinsamer Designkatalog</h1>\n"
        f"<p class=\"lead\">{len(profiles)} Designs &middot; {hell} hell, "
        f"{len(profiles) - hell} dunkel &middot; {len(ALL_ROLES)} Rollen je Design. "
        f"Dieselben Dateien liegen in LifePlanner, BudgetManager, FountainPen Manager "
        f"und FreizeitManager. Jede Karte zeigt die Signalfarben zusaetzlich so, wie "
        f"sie bei Rot-, Gruen- und Blauschwaeche erscheinen - dort muessen sie "
        f"unterscheidbar bleiben.</p>\n"
        f"<div class=\"grid\">\n{cards}\n</div>\n",
        encoding="utf-8")
    print(f"{len(profiles)} Designs -> {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("befehl", choices=("build", "check", "preview", "new"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="Ordner, der die vier Programme enthaelt")
    parser.add_argument("--dir", type=Path, help="Profilverzeichnis fuer check")
    parser.add_argument("--name", help="Name des neuen Designs")
    parser.add_argument("--modus", default="hell", choices=("hell", "dunkel"))
    parser.add_argument("--akzent", help="Akzentfarbe, z. B. #2563eb")
    parser.add_argument("--grund", help="Grundfarbe; ohne Angabe aus dem Akzent abgeleitet")
    parser.add_argument("--out", type=Path,
                        help="Zieldatei fuer preview")
    parser.add_argument("--only", action="append", choices=sorted(TARGETS),
                        help="nur dieses Programm schreiben")
    args = parser.parse_args(argv)

    if args.befehl == "build":
        return build(args.repo_root, args.only)
    if args.befehl == "new":
        if not (args.name and args.akzent):
            parser.error("new braucht --name und --akzent")
        return create(args.name, args.modus, args.akzent, args.grund,
                      args.repo_root, args.only)
    target = args.dir or local_profile_dir()
    if target is None:
        parser.error("Kein Profilverzeichnis gefunden - bitte --dir angeben")
    if args.befehl == "preview":
        return preview(target, args.out or Path("designkatalog.html"))
    return check(target)


if __name__ == "__main__":
    raise SystemExit(main())
