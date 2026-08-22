"""Die Oberflaeche waechst mit der eingestellten Schriftgroesse.

Warum es das braucht: Die Schriftgroesse steht im Designprofil. Feste
Pixelwerte im Stylesheet setzen sich darueber hinweg - wer die Schrift zur
besseren Lesbarkeit hochstellt, bekommt dann groesseren Text in unveraendert
engen Feldern. Genau das war hier der Fall: Der Cockpit-Titel stand fest bei
22px und wuchs gar nicht mit.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""

from __future__ import annotations

import re

import pytest

from theme_manager import ThemeManager


class _Settings(dict):
    def set(self, key, value):
        self[key] = value


@pytest.fixture(scope="module")
def manager() -> ThemeManager:
    return ThemeManager(_Settings())


def _stylesheet(manager: ThemeManager, schriftgroesse: int) -> str:
    profil = manager.get_current_profile()
    profil.data["schriftgroesse"] = schriftgroesse
    return manager.build_stylesheet(profil)


def _groessen(css: str, eigenschaft: str) -> list[int]:
    return [int(x) for x in re.findall(rf"{eigenschaft}:\s*(\d+)px", css)]


@pytest.mark.parametrize("eigenschaft", ["font-size", "min-height", "border-radius"])
def test_die_masse_wachsen_mit_der_schrift(manager, eigenschaft):
    klein = _groessen(_stylesheet(manager, 8), eigenschaft)
    gross = _groessen(_stylesheet(manager, 16), eigenschaft)
    assert klein and len(klein) == len(gross), f"{eigenschaft} nicht vergleichbar"
    assert (
        sum(gross) > sum(klein) * 1.3
    ), f"{eigenschaft} waechst kaum mit: {sum(klein)} -> {sum(gross)}"


def test_der_cockpit_titel_waechst_mit(manager):
    """Er stand fest bei 22px und ueberschrieb damit die Profilschrift."""
    treffer = [
        int(
            re.search(
                r"QLabel#cockpitTitle[^}]*font-size:\s*(\d+)px", _stylesheet(manager, g)
            ).group(1)
        )
        for g in (8, 10, 16)
    ]
    assert treffer[0] < treffer[1] < treffer[2], treffer


def test_bei_standardgroesse_bleibt_alles_wie_bisher(manager):
    """Der Auslieferungszustand darf sich durch die Skalierung nicht aendern.

    BudgetManager ist die Design-Vorlage der Suite - sein Aussehen bei 10pt
    ist der Massstab, an dem sich die anderen ausrichten.
    """
    css = _stylesheet(manager, 10)
    for erwartet in (
        "font-size: 22px",
        "min-height: 22px",
        "border-radius: 11px",
        "border-radius: 6px",
        "border-radius: 4px",
        "border-radius: 8px",
        "border-radius: 10px",
        "border-radius: 12px",
    ):
        assert erwartet in css, erwartet
