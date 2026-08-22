#!/usr/bin/env python3
"""Enterprise-UI-/Usability-/ADHS-Audit – 10 Domänen × 100 = 1000 Loops.

Headless und deterministisch. Wo möglich werden ECHTE Funktionen aufgerufen
(Destruktiv-Erkennung, Preset-/Migrationslogik, i18n); Qt-gebundene Regeln
werden als Quell-Invarianten geprüft. Jede Domäne liefert 100 Loops mit je
mehreren Checks.

 D1  destructive_text  – Enter-Sicherheit: Golden-Set aus 3 Sprachen gegen die
                         zentrale Erkennung (keine False-Negatives wie
                         'réinitialiser', keine False-Positives wie 'Preset').
 D2  a11y_i18n         – Keine hartkodierten deutschen A11y-/UI-Sätze ausserhalb tr().
 D3  filter_hygiene    – Show-Filter: Einmal-Marker pro Widgetbaum, Popup/Menü-Skip,
                         zerstörungssicherer Fokus-Timer (RuntimeError-Guard).
 D4  focus_rules       – Kein Erstfokus/Default auf destruktiven Buttons (Quellscan).
 D5  cockpit_presets   – ECHTE Läufe der Preset-/Migrationslogik: Neuinstallation
                         startet materialisiert im Fokus; Bestand bleibt unangetastet
                         (custom); Panel-Toggle im Fokus ändert GENAU ein Panel;
                         v2014-Zwang kippt kein Preset.
 D6  i18n_placeholders – {Platzhalter} je Key identisch über de/en/fr.
 D7  i18n_refs         – Jeder tr()-Key aus utils/views existiert in allen Sprachen.
 D8  dialog_scaling    – Kein setFixedSize auf Dialog-/Fensterklassen (200 %-Skalierung).
 D9  icon_buttons      – Icon-/Emoji-only-Buttons besitzen Tooltip (A11y-Fallbackquelle).
 D10 enter_defaults    – Kein setDefault(True)/setAutoDefault(True) auf destruktiven
                         Buttons im Quelltext.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FINDINGS: list[str] = []
CHECKS = 0


def check(cond: bool, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FINDINGS.append(msg)
        print(f"  ❌ {msg}")


def _flat(d, p=""):
    o = {}
    for k, v in d.items():
        nk = f"{p}.{k}" if p else k
        if isinstance(v, dict):
            o.update(_flat(v, nk))
        else:
            o[nk] = v
    return o


LOCALES = {
    lang: _flat(
        json.loads((ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
    )
    for lang in ("de", "en", "fr")
}
VIEW_FILES = sorted(
    [p for p in (ROOT / "views").rglob("*.py")] + [ROOT / "utils" / "ui_usability.py"]
)
TR_KEY_RE = re.compile(r"\b(?:tr|trf)\(\s*['\"]([A-Za-z0-9_.]+)['\"]")


# ── D1: Destruktiv-Erkennung (echte Funktion, Golden-Set) ──────────────────
GOLDEN_DESTRUCTIVE = [
    "Löschen",
    "Alle löschen",
    "Eintrag entfernen",
    "Zurücksetzen…",
    "Datenbank zurücksetzen",
    "Verwerfen",
    "Delete",
    "Remove all",
    "Clear list",
    "Reset",
    "Discard changes",
    "Supprimer",
    "Tout supprimer",
    "Effacer",
    "Réinitialiser",
    "Retirer",
    "Vider la liste",
]
GOLDEN_SAFE = [
    "Speichern",
    "Preset speichern",
    "Presets",
    "Übernehmen",
    "Schliessen",
    "Save",
    "Apply preset",
    "Close",
    "Enregistrer",
    "Préréglages",
    "OK",
    "Buchen",
    "Exportieren",
    "Importieren",
    "Wiederherstellen",
]


def d1_destructive(rng, i):
    try:
        from utils.ui_text_rules import is_destructive_text
    except ImportError:
        check(
            False,
            f"[D1 L{i}] is_destructive_text nicht Qt-frei verfügbar (Extraktion fehlt)",
        )
        return
    pos = rng.sample(GOLDEN_DESTRUCTIVE, 4)
    neg = rng.sample(GOLDEN_SAFE, 4)
    for t in pos:
        check(is_destructive_text(t), f"[D1 L{i}] nicht erkannt: {t!r}")
    for t in neg:
        check(not is_destructive_text(t), f"[D1 L{i}] False-Positive: {t!r}")


# ── D2: keine hartkodierten deutschen UI-Sätze ─────────────────────────────
_GERMAN_HINTS = re.compile(
    r'"[^"\n]*(Pfeiltasten|navigieren|öffnet die Auswahl|Mit Enter)[^"\n]*"'
)


def d2_a11y_i18n(rng, i):
    f = VIEW_FILES[i % len(VIEW_FILES)]
    text = f.read_text(encoding="utf-8")
    for m in _GERMAN_HINTS.finditer(text):
        line = text[: m.start()].count("\n") + 1
        seg = text[max(0, m.start() - 40) : m.start()]
        if "tr(" in seg or "trf(" in seg:
            continue
        check(
            False,
            f"[D2 L{i}] {f.relative_to(ROOT)}:{line} hartkodierter deutscher UI-Satz",
        )
    check(True, "")  # zählt den Datei-Scan als Check


# ── D3: Filter-Hygiene (Quell-Invarianten) ─────────────────────────────────
def d3_filter_hygiene(rng, i):
    src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
    aspects = [
        (
            "_bm_ui_enhanced",
            "Einmal-Marker pro Widget fehlt (O(n) bei JEDEM Show, auch Combo-Popups)",
        ),
        ("Popup", "Popup-/Menü-Fenster werden nicht übersprungen"),
        ("RuntimeError", "Fokus-Timer ohne Guard gegen bereits zerstörten Dialog"),
        ("isVisible", "Fokus-Timer prüft Sichtbarkeit nicht"),
    ]
    key, msg = aspects[i % len(aspects)]
    check(key in src, f"[D3 L{i}] {msg}")


# ── D4: kein Fokus/Default auf destruktiven Buttons ────────────────────────
_FOCUS_ON = re.compile(
    r"self\.(btn_[a-z_]*(?:delete|loesch|remove|reset)[a-z_]*)\.(setFocus|setDefault)\("
)


def d4_focus_rules(rng, i):
    f = VIEW_FILES[i % len(VIEW_FILES)]
    text = f.read_text(encoding="utf-8")
    for m in _FOCUS_ON.finditer(text):
        if "setDefault(False)" in text[m.start() : m.end() + 8]:
            continue
        check(False, f"[D4 L{i}] {f.name}: {m.group(0)} auf destruktivem Button")
    check(True, "")


# ── D5: Preset-/Migrationslogik (echte Läufe) ──────────────────────────────
class _MemSettings:
    def __init__(self, initial=None):
        self.d = dict(initial or {})

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


def d5_cockpit_presets(rng, i):
    try:
        from utils import cockpit_presets as cp
    except ImportError:
        check(
            False,
            f"[D5 L{i}] utils/cockpit_presets fehlt – Preset-Logik nicht Qt-frei prüfbar; "
            f"Neuinstallation materialisiert v2014-ALL-TRUE statt Fokus",
        )
        return
    # a) Neuinstallation: focus materialisiert, v2014 kippt nichts
    s = _MemSettings({"cockpit_preset": "focus"})
    cp.materialize_initial(s)
    cp.migrate_v2014(s)
    eff = cp.effective_panels(s)
    check(
        eff == cp.PRESETS["focus"],
        f"[D5 L{i}] Neuinstallation zeigt nicht Fokus: {eff}",
    )
    check(
        s.get("cockpit_preset") == "focus",
        f"[D5 L{i}] Preset gekippt: {s.get('cockpit_preset')}",
    )
    # b) Bestand mit eigener Config bleibt unangetastet (custom)
    own = {k: rng.random() < 0.5 for k in cp.PANEL_KEYS}
    s2 = _MemSettings(
        {
            "cockpit_visible_panels": dict(own),
            "cockpit_preset": "custom",
            "cockpit_warnings_visible_migrated_v2014": True,
        }
    )
    cp.materialize_initial(s2)
    check(s2.get("cockpit_visible_panels") == own, f"[D5 L{i}] Bestand überschrieben")
    # c) Toggle im Fokus ändert GENAU ein Panel
    s3 = _MemSettings({"cockpit_preset": "focus"})
    cp.materialize_initial(s3)
    key = rng.choice(list(cp.PANEL_KEYS))
    before = cp.effective_panels(s3)
    cp.set_panel(s3, key, not before[key])
    after = cp.effective_panels(s3)
    diff = [k for k in cp.PANEL_KEYS if before[k] != after[k]]
    check(diff == [key], f"[D5 L{i}] Toggle {key} änderte {diff}")
    check(s3.get("cockpit_preset") == "custom", f"[D5 L{i}] Toggle setzt kein custom")
    # d) v2014-Migration nur bei Bestand mit Config UND custom
    s4 = _MemSettings({"cockpit_preset": "focus"})
    cp.materialize_initial(s4)
    cp.migrate_v2014(s4)
    check(
        cp.effective_panels(s4)["action_needed"]
        == cp.PRESETS["focus"]["action_needed"],
        f"[D5 L{i}] v2014 erzwingt Panels gegen das Fokus-Preset",
    )


# ── D6: Platzhalter-Parität ────────────────────────────────────────────────
_PH = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def d6_placeholders(rng, i):
    keys = sorted(set(LOCALES["de"]) & set(LOCALES["en"]) & set(LOCALES["fr"]))
    sample = keys[i::100]
    for k in sample:
        ph = {
            lang: sorted(_PH.findall(str(LOCALES[lang].get(k, ""))))
            for lang in ("de", "en", "fr")
        }
        check(
            ph["de"] == ph["en"] == ph["fr"],
            f"[D6 L{i}] Platzhalter-Divergenz {k}: {ph}",
        )


# ── D7: alle referenzierten Keys existieren ────────────────────────────────
def d7_refs(rng, i):
    f = VIEW_FILES[i % len(VIEW_FILES)]
    text = f.read_text(encoding="utf-8")
    for key in set(TR_KEY_RE.findall(text)):
        for lang in ("de", "en", "fr"):
            check(
                key in LOCALES[lang], f"[D7 L{i}] {f.name}: Key fehlt in {lang}: {key}"
            )


# ── D8: Skalierung ─────────────────────────────────────────────────────────
def d8_scaling(rng, i):
    f = VIEW_FILES[i % len(VIEW_FILES)]
    text = f.read_text(encoding="utf-8")
    for m in re.finditer(r"self\.setFixedSize\(", text):
        line = text[: m.start()].count("\n") + 1
        check(
            False,
            f"[D8 L{i}] {f.relative_to(ROOT)}:{line} setFixedSize blockiert Skalierung/Resize",
        )
    check(True, "")


# ── D9: Icon-only-Buttons brauchen Tooltip ────────────────────────────────
_EMOJI_ONLY = re.compile(
    r'(self\.[a-z_]+)\s*=\s*QPushButton\(\s*(?:get_icon\([^)]*\)\s*,\s*)?["\']'
    r'([\u2190-\u2BFF\U0001F000-\U0001FAFF◀▶✚✖✗✓+×\-]{1,3})["\']\s*\)'
)


def d9_icon_buttons(rng, i):
    f = VIEW_FILES[i % len(VIEW_FILES)]
    text = f.read_text(encoding="utf-8")
    for m in _EMOJI_ONLY.finditer(text):
        var = m.group(1)
        has_tip = f"{var}.setToolTip(" in text or f"{var}.setAccessibleName(" in text
        line = text[: m.start()].count("\n") + 1
        check(
            has_tip,
            f"[D9 L{i}] {f.relative_to(ROOT)}:{line} Icon-Button {var} ohne Tooltip/A11y-Name",
        )
    check(True, "")


# ── D10: kein Default auf destruktiven Buttons (Quelle) ────────────────────
def d10_enter_defaults(rng, i):
    f = VIEW_FILES[i % len(VIEW_FILES)]
    text = f.read_text(encoding="utf-8")
    for m in re.finditer(r"self\.(btn_[a-z_]+)\.set(?:Auto)?Default\(True\)", text):
        var = m.group(1)
        destructive = any(
            w in var for w in ("delete", "loesch", "remove", "reset", "clear")
        )
        check(not destructive, f"[D10 L{i}] {f.name}: {var} als Enter-Default")
    check(True, "")


DOMAINS = [
    d1_destructive,
    d2_a11y_i18n,
    d3_filter_hygiene,
    d4_focus_rules,
    d5_cockpit_presets,
    d6_placeholders,
    d7_refs,
    d8_scaling,
    d9_icon_buttons,
    d10_enter_defaults,
]


def main() -> int:
    import sys as _sys

    csv_path = None
    if "--csv" in _sys.argv:
        csv_path = _sys.argv[_sys.argv.index("--csv") + 1]
    rows = []
    rng = random.Random(2221)
    loop = 0
    for rounds in range(100):
        for dom in DOMAINS:
            loop += 1
            c0, f0 = CHECKS, len(FINDINGS)
            try:
                dom(rng, loop)
            except Exception as e:
                FINDINGS.append(
                    f"[{dom.__name__} L{loop}] EXCEPTION {type(e).__name__}: {e}"
                )
                print(f"  💥 {dom.__name__} L{loop}: {type(e).__name__}: {e}")
            rows.append(
                (
                    loop,
                    dom.__name__,
                    CHECKS - c0,
                    "FAIL" if len(FINDINGS) > f0 else "PASS",
                )
            )
        if (rounds + 1) % 20 == 0:
            print(f"Loop {loop:04d}: checks={CHECKS} findings={len(FINDINGS)}")
    if csv_path:
        import csv as _csv

        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["loop", "domain", "checks", "result"])
            w.writerows(rows)
        print(f"CSV: {csv_path} ({len(rows)} Zeilen)")
    uniq = sorted(set(FINDINGS))
    print(
        f"\n=== UI/ADHS-AUDIT {loop} LOOPS DONE: checks={CHECKS} "
        f"findings={len(FINDINGS)} (unique {len(uniq)}) ==="
    )
    for u in uniq[:20]:
        print("   •", u)
    return 1 if FINDINGS else 0


if __name__ == "__main__":
    raise SystemExit(main())
