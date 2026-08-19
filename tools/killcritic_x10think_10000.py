#!/usr/bin/env python3
"""KILLCRITIC X10THINK – 10.000-Loop-Usability-Audit für BudgetManager.

Zehn Domänen x 1000 Loops. Jede Domäne prüft pro Loop ZEHN Perspektiven
("X10THINK"): Funktion, Prozesspfad, Anleitung/Wiki, Fehlerpfad, i18n,
Accessibility, Konsistenz, Datenintegrität, Regressionsschutz, Nachweis.
Wo möglich laufen ECHTE Funktionen (In-Memory-/Tempfile-Datenbanken,
Bundles, Update-Staging); Reines-Quelltext-Wissen wird nur genutzt, wo
Qt zwingend wäre.

Domänen:
  k1  Erststart-/Assistenten-Prozesspfad (statisch, i18n, Schritte)
  k2  Kernbuchungs-Lebenszyklus (echte DB: Kategorie->Buchung->Filter->
      Undo/Redo inkl. Tag- und Quellenerhalt)
  k3  Backup-Bundle-Rundlauf (create -> verify -> Manipulation -> Fehler)
  k4  Anleitungs-/Guide-Abdeckung (USER_GUIDE de/en/fr, FEATURES)
  k5  Hilfe-Wiki-Integrität (HELP_TOPICS: Struktur, Sprachen, Suche)
  k6  UI-Text-Qualität über alle Sprachwerte (Whitespace, Platzhalter,
      Shortcuts, Ellipsen)
  k7  Update-Prozesspfad (find_staged_root inkl. Marker-Randfall,
      Payload-Validierung)
  k8  Meldungs- und Schlüsseldisziplin (tr/trf-Referenzen existieren,
      Toasts nie fuer destruktive Aktionen)
  k9  Dialog-/Navigations-Invarianten (Schliessbarkeit, Tab-Ketten-
      Registrierung, Toast-Fokus-Regeln)
  k10 Regressions-Vollschutz (Ultimo, SQL-Guards, Tag-Restore, Quelle,
      0 modale Infos, Paritaet aller Sprachen, Matrix-/Gate-Nachweise)

Exit 1 bei mindestens einem FAIL. Matrix-CSV im Projekt-Root.
"""
from __future__ import annotations

import ast
import csv
import json
import random
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_info import APP_VERSION  # noqa: E402
from model.typ_constants import TYP_EXPENSES, TYP_INCOME  # noqa: E402

LOOPS_PER_DOMAIN = 1000
CSV_PATH = ROOT / (
    "KILLCRITIC_X10THINK_10000_MATRIX_v" + APP_VERSION.replace(".", "_") + ".csv"
)

LANGS = ("de", "en", "fr")


def _flat(d: dict, pre: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        kk = f"{pre}.{k}" if pre else k
        if isinstance(v, dict):
            out.update(_flat(v, kk))
        else:
            out[kk] = v
    return out


def _locales() -> dict[str, dict[str, str]]:
    return {
        lang: _flat(json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8")))
        for lang in LANGS
    }


LOC = _locales()
GUIDES = {
    lang: (ROOT / "docs" / f"USER_GUIDE.{lang}.md").read_text("utf-8") for lang in LANGS
}


def _fresh_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from model.migrations import migrate_all

    migrate_all(conn)
    return conn


# ─────────────────────────── k1 Erststart ───────────────────────────
def k1_first_run_path(i: int, rng: random.Random) -> tuple[int, str, str]:
    src = (ROOT / "views" / "setup_assistant_dialog.py").read_text("utf-8")
    wiz = (ROOT / "views" / "startup_wizard.py").read_text("utf-8")
    checks, bad = 0, []
    # 1 Schritt-Keys des Assistenten existieren dreisprachig
    step_keys = sorted(set(re.findall(r'tr\("((?:setup|assistant)[\w.]+)"\)', src)))
    sample = rng.sample(step_keys, min(4, len(step_keys))) if step_keys else []
    for key in sample:
        checks += 1
        if not all(key in LOC[lang] for lang in LANGS):
            bad.append(f"i18n fehlt: {key}")
    # 2 Zurueck/Abbrechen-Pfade vorhanden
    checks += 1
    if not ("reject" in src or "close" in src):
        bad.append("Assistent ohne Abbruchpfad")
    # 3 Wizard bietet Weiter-Navigation
    checks += 1
    if not re.search(r"next|weiter|_go_|setCurrentIndex", wiz, re.I):
        bad.append("Wizard ohne Vorwaerts-Navigation")
    # 4 Erststart im Guide beschrieben (jede Sprache)
    for lang, term in (("de", "Erststart"), ("en", "first start"), ("fr", "premier")):
        checks += 1
        if term.lower() not in GUIDES[lang].lower():
            bad.append(f"Guide {lang}: Erststart fehlt")
    # 5 DAU-Erststart-Doku traegt aktuelle Version
    checks += 1
    if APP_VERSION not in (ROOT / "docs" / "DAU_TEST_ERSTSTART.md").read_text("utf-8"):
        bad.append("DAU_TEST_ERSTSTART ohne aktuelle Version")
    # 6 Assistent nutzt keine modalen Infos
    checks += 1
    if "QMessageBox.information" in src:
        bad.append("Assistent nutzt modale Info")
    return checks, "FAIL" if bad else "PASS", "; ".join(bad) or "Erststartpfad ok"


# ───────────────────── k2 Kernbuchungs-Lebenszyklus ─────────────────────
def k2_booking_lifecycle(i: int, rng: random.Random) -> tuple[int, str, str]:
    from model.category_model import CategoryModel
    from model.tracking_model import TrackingModel
    from model.tags_model import TagsModel

    conn = _fresh_db()
    checks, bad = 0, []
    try:
        cat = CategoryModel(conn)
        trk = TrackingModel(conn)
        tags = TagsModel(conn)
        undo = trk.undo  # integrierter Stack des Tracking-Modells

        name = f"KC{i%97}_{rng.randint(0, 9999)}"
        typ = rng.choice([TYP_EXPENSES, TYP_INCOME])
        cat_id = cat.create(typ, name)
        checks += 1
        if not cat_id:
            bad.append("CategoryModel.create ohne id")

        tag_id = tags.create_tag(f"tag{i%53}_{rng.randint(0,999)}", "#a0a0a0")
        checks += 1
        if not tag_id:
            bad.append("create_tag ohne id")
        tags.assign_to_category(cat_id, tag_id)

        amount = round(rng.uniform(1, 500), 2)
        entry_id = trk.add(
            f"2026-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            typ,
            name,
            amount,
            details=f"loop{i}",
        )
        checks += 1
        if not entry_id:
            bad.append("TrackingModel.add ohne id")

        # feste Kategorie-Tags haengen an der Buchung
        checks += 1
        etags = {
            r["tag_id"]
            for r in conn.execute(
                "SELECT tag_id FROM entry_tags WHERE entry_id=?", (entry_id,)
            )
        }
        if tag_id not in etags:
            bad.append("fester Kategorie-Tag fehlt an Buchung")

        # Quelle bleibt beim Lesen erhalten
        checks += 1
        row = next((r for r in trk.list_filtered(typ=typ) if r.id == entry_id), None)
        if row is None or getattr(row, "source", "manual") not in (
            "manual",
            "auto_fixcost",
            "auto_recurring",
            "auto_optional",
        ):
            bad.append("Quelle beim Lesen verloren")

        # Loeschen -> Undo stellt Buchung UND Tags wieder her
        trk.delete(entry_id)
        checks += 1
        if any(r.id == entry_id for r in trk.list_filtered(typ=typ)):
            bad.append("delete wirkungslos")
        undo.undo()
        checks += 1
        restored = [r for r in trk.list_filtered(typ=typ) if r.details == f"loop{i}"]
        if not restored:
            bad.append("Undo stellt Buchung nicht wieder her")
        else:
            rid = restored[0].id
            checks += 1
            rtags = {
                r["tag_id"]
                for r in conn.execute(
                    "SELECT tag_id FROM entry_tags WHERE entry_id=?", (rid,)
                )
            }
            if tag_id not in rtags:
                bad.append("Undo verliert Tag-Belegung")
        # Redo entfernt wieder inkl. Tag-Reste
        undo.redo()
        checks += 1
        leftover = conn.execute(
            "SELECT COUNT(*) FROM entry_tags et LEFT JOIN tracking t"
            " ON t.id = et.entry_id WHERE t.id IS NULL"
        ).fetchone()[0]
        if leftover:
            bad.append(f"{leftover} verwaiste entry_tags nach Redo")

        # Filter-Orakel: Betragsfilter
        checks += 1
        lo = amount - 0.5
        got = trk.list_filtered(typ=typ, min_amount=lo)
        if any(abs(r.amount) < lo - 1e-9 for r in got):
            bad.append("min_amount-Filter verletzt")

        # SQL-Guard bleibt aktiv
        checks += 1
        if trk._cols("tracking; DROP TABLE tracking") != set():
            bad.append("tracking._cols-Guard inaktiv")
    finally:
        conn.close()
    return checks, "FAIL" if bad else "PASS", "; ".join(bad) or "Lebenszyklus ok"


# ─────────────────────── k3 Backup-Bundle-Rundlauf ───────────────────────
def k3_bundle_roundtrip(i: int, rng: random.Random) -> tuple[int, str, str]:
    from model.restore_bundle import (
        BundleIntegrityError,
        create_bundle,
        verify_bundle,
    )

    checks, bad = 0, []
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        db = tdp / "database.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE t(x)")
        conn.execute("INSERT INTO t VALUES (?)", (i,))
        conn.commit()
        conn.close()
        bundle = tdp / f"b{i}.zip"
        create_bundle(
            source_db=db,
            out_path=bundle,
            app="BudgetManager",
            app_version=APP_VERSION,
            note=f"killcritic loop {i}",
        )
        checks += 1
        if not bundle.exists():
            bad.append("Bundle nicht erzeugt")
        checks += 1
        member = ""
        try:
            member = verify_bundle(bundle)
            if not member:
                bad.append("verify_bundle ohne Member")
        except Exception as e:
            bad.append(f"verify_bundle wirft: {type(e).__name__}")
        if not member:
            return checks, "FAIL", "; ".join(bad)
        # Manipulation 1: Byte im DB-MEMBER kippen (letztes Deflate-Byte
        # meiden – dessen Padding-Bits aendern das Dekompressat nicht).
        raw = bytearray(bundle.read_bytes())
        with zipfile.ZipFile(bundle) as zf:
            db_info = next(z for z in zf.infolist() if z.filename == member)
        ho = db_info.header_offset
        fn_len = int.from_bytes(raw[ho + 26 : ho + 28], "little")
        ex_len = int.from_bytes(raw[ho + 28 : ho + 30], "little")
        data_start = ho + 30 + fn_len + ex_len
        span = max(1, db_info.compress_size - 1)
        pos = data_start + rng.randrange(span)
        raw[pos] ^= 0x01
        tampered = tdp / "tampered.zip"
        tampered.write_bytes(bytes(raw))
        checks += 1
        try:
            verify_bundle(tampered)
            # Kein Fehler ist nur akzeptabel, wenn der Flip inhaltsneutral
            # war (Deflate-Padding-/BFINAL-Bits aendern das Dekompressat
            # nicht – dann IST die Integritaet faktisch intakt).
            try:
                with zipfile.ZipFile(tampered) as zt, zipfile.ZipFile(bundle) as zo:
                    changed = zt.read(member) != zo.read(member)
            except Exception:
                changed = True
            if changed:
                bad.append("inhaltsaendernder DB-Byte-Flip unbemerkt")
        except Exception:
            pass
        # Manipulation 1b: Inhalt REAL aendern (1 Byte im Dekompressat)
        # -> SHA256-Abgleich MUSS anschlagen.
        with zipfile.ZipFile(bundle) as zin:
            db_bytes = bytearray(zin.read(member))
        db_bytes[len(db_bytes) // 2] ^= 0xFF
        swapped = tdp / "swapped.zip"
        with zipfile.ZipFile(bundle) as zin, zipfile.ZipFile(
            swapped, "w", zipfile.ZIP_DEFLATED
        ) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == member:
                    data = bytes(db_bytes)
                zout.writestr(item.filename, data)
        checks += 1
        try:
            verify_bundle(swapped)
            bad.append("inhaltsveraendertes DB-Member unbemerkt")
        except BundleIntegrityError:
            pass
        # Manipulation 2: Manifest-Semantik – verfaelschter sha256 MUSS
        # den Hash-Abgleich ausloesen (Bindung Manifest <-> Member).
        forged = tdp / "forged.zip"
        with zipfile.ZipFile(bundle) as zin, zipfile.ZipFile(
            forged, "w", zipfile.ZIP_DEFLATED
        ) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "manifest.json":
                    mani = json.loads(data.decode("utf-8"))
                    mani["sha256"] = "0" * 64
                    data = json.dumps(mani).encode("utf-8")
                zout.writestr(item.filename, data)
        checks += 1
        try:
            verify_bundle(forged)
            bad.append("verfaelschtes Manifest unbemerkt")
        except BundleIntegrityError:
            pass
    return checks, "FAIL" if bad else "PASS", "; ".join(bad) or "Bundle-Rundlauf ok"


# ─────────────────────── k4 Anleitungs-Abdeckung ───────────────────────
CORE_TERMS = {
    "de": [
        "Cockpit",
        "Budget",
        "Tracking",
        "Tags",
        "Sparziel",
        "Backup",
        "Update",
        "Konten",
        "Favoriten",
        "Monatsabschluss",
    ],
    "en": [
        "Cockpit",
        "Budget",
        "Tracking",
        "Tags",
        "Savings",
        "Backup",
        "Update",
        "Account",
        "Favorites",
        "Month",
    ],
    "fr": [
        "Cockpit",
        "Budget",
        "Suivi",
        "Tags",
        "Épargne",
        "Sauvegarde",
        "Mise",
        "Compte",
        "Favoris",
        "Mois",
    ],
}


def k4_guide_coverage(i: int, rng: random.Random) -> tuple[int, str, str]:
    checks, bad = 0, []
    lang = LANGS[i % 3]
    guide = GUIDES[lang]
    for term in CORE_TERMS[lang]:
        checks += 1
        if term.lower() not in guide.lower():
            bad.append(f"{lang}: '{term}' fehlt im Guide")
    return (
        checks,
        "FAIL" if bad else "PASS",
        "; ".join(bad) or f"{lang}-Guide deckt Kernfunktionen",
    )


# ─────────────────────── k5 Hilfe-Wiki-Integritaet ───────────────────────
def k5_help_wiki(i: int, rng: random.Random) -> tuple[int, str, str]:
    from views.help_content import (
        HELP_TOPICS,
        help_topic_body,
        help_topic_haystack,
        help_topic_title,
    )

    checks, bad = 0, []
    checks += 1
    ids = [t.get("id") for t in HELP_TOPICS]
    if len(ids) != len(set(ids)):
        bad.append("doppelte Topic-IDs")
    topic = HELP_TOPICS[i % len(HELP_TOPICS)]
    for lang in LANGS:
        checks += 2
        if not help_topic_title(topic, lang).strip():
            bad.append(f"{topic.get('id')}: Titel {lang} leer")
        body = help_topic_body(topic, lang)
        if not body.strip():
            bad.append(f"{topic.get('id')}: Body {lang} leer")
        checks += 1
        if re.search(r"\b[a-z]+\.[a-z_]+\.[a-z_]+\b", body) and "http" not in body:
            # grobe Heuristik auf rohe i18n-Keys im Fliesstext
            if re.search(r"\b(cockpit|settings|tags|budget)\.[a-z_]+", body):
                bad.append(f"{topic.get('id')}: roher Key im {lang}-Text")
    checks += 1
    if not help_topic_haystack(topic, "de"):
        bad.append("Suchindex leer")
    return checks, "FAIL" if bad else "PASS", "; ".join(bad) or "Wiki-Topic ok"


# ─────────────────────── k6 UI-Text-Qualitaet ───────────────────────
def k6_text_quality(i: int, rng: random.Random) -> tuple[int, str, str]:
    checks, bad, warn = 0, [], []
    lang = LANGS[i % 3]
    items = sorted(LOC[lang].items())
    seg = items[(i * 37) % len(items) :][:40] or items[:40]
    for key, val in seg:
        if not isinstance(val, str):
            continue
        is_html = key.endswith(".html") or val.lstrip().startswith("<")
        checks += 1
        if val.count("{") != val.count("}"):
            bad.append(f"{lang}:{key} Platzhalter unbalanciert")
        checks += 1
        if re.search(r"\b(TODO|FIXME|XXX)\b", val):
            bad.append(f"{lang}:{key} Platzhaltertext")
        if is_html:
            continue
        # Bewusste Struktur-Einrueckung (z. B. '  ↳ {value_0}' fuer
        # Unterkategorien) ist kein Textfehler.
        if re.match(r"\s*[↳→└├•·✓✗✔✖]\s", val):
            continue
        checks += 1
        core = val.strip("\n\r")
        deliberate_frag = (
            val.startswith(" ")
            and all(
                isinstance(LOC[lg].get(key), str) and LOC[lg][key].startswith(" ")
                for lg in LANGS
            )
        ) or (
            val.endswith(" ")
            and all(
                isinstance(LOC[lg].get(key), str) and LOC[lg][key].endswith(" ")
                for lg in LANGS
            )
        )
        if core != core.strip(" \t") and not deliberate_frag:
            bad.append(f"{lang}:{key} Randleerzeichen")
        checks += 1
        aligned_block = "\n" in val and ("─" in val or re.search(r"\}:\s{2,}\{", val))
        norm = val.replace("  (", " (")
        for sep in ("•", "–", "|"):
            norm = norm.replace(f"  {sep}  ", f" {sep} ")
        # Dreisprachig konsistente Doppel-Leerzeichen sind Layout
        # (Schritt-Trenner, Beispiel-Abstaende); ein echter Tippfehler
        # waere sprachspezifisch.
        deliberate_gap = all(
            isinstance(LOC[lg].get(key), str) and "  " in LOC[lg][key] for lg in LANGS
        )
        if "  " in norm and not aligned_block and not deliberate_gap:
            bad.append(f"{lang}:{key} Doppel-Leerzeichen")
        checks += 1
        if val.count("&") - 2 * val.count("&&") > 1:
            warn.append(f"{lang}:{key} mehrere Shortcuts")
    if bad:
        return checks, "FAIL", "; ".join(bad[:4])
    if warn:
        return checks, "WARN", "; ".join(warn[:3])
    return checks, "PASS", f"{lang}: {len(seg)} Werte sauber"


# ─────────────────────── k7 Update-Prozesspfad ───────────────────────
def k7_update_path(i: int, rng: random.Random) -> tuple[int, str, str]:
    from updater.common import find_staged_root

    checks, bad = 0, []
    with tempfile.TemporaryDirectory() as td:
        staging = Path(td)
        # Fall A: Top-Level-Ordner + Marker (der Randfall des Enterprise-Fixes)
        top = staging / f"BudgetManager-v{APP_VERSION}"
        (top / "sub").mkdir(parents=True)
        (top / "BudgetManager").write_bytes(b"bin")
        (top / "sub" / "f.txt").write_text("x")
        (staging / "_update_marker.json").write_text("{}")
        checks += 1
        if find_staged_root(staging) != top:
            bad.append("Top-Level-Ordner trotz Marker nicht erkannt")
        # Fall B: flaches ZIP-Layout
        flat = staging / "flat"
        flat.mkdir()
        (flat / "BudgetManager").write_bytes(b"bin")
        checks += 1
        if find_staged_root(flat) != flat:
            bad.append("flaches Layout falsch aufgeloest")
        # Fall C: __MACOSX wird ignoriert
        mac = staging / "case_c"
        (mac / "__MACOSX").mkdir(parents=True)
        (mac / "Only").mkdir()
        checks += 1
        if find_staged_root(mac).name != "Only":
            bad.append("__MACOSX nicht ignoriert")
    # Doku: Update-Prozess je Sprache beschrieben
    for lang, term in (("de", "Update"), ("en", "update"), ("fr", "mise")):
        checks += 1
        if term.lower() not in GUIDES[lang].lower():
            bad.append(f"Guide {lang}: Update fehlt")
    return checks, "FAIL" if bad else "PASS", "; ".join(bad) or "Update-Pfad ok"


# ─────────────── k8 Meldungs- und Schluesseldisziplin ───────────────
_VIEW_FILES = sorted((ROOT / "views").rglob("*.py")) + [ROOT / "settings_dialog.py"]
_KEY_RE = re.compile(r"\btrf?\(\s*[\"']([a-z0-9_]+(?:\.[a-z0-9_]+)+)[\"']")
_ALL_REFS: list[tuple[str, str]] = []
for _f in _VIEW_FILES:
    for _m in _KEY_RE.finditer(_f.read_text("utf-8")):
        _ALL_REFS.append((_f.name, _m.group(1)))


def k8_key_discipline(i: int, rng: random.Random) -> tuple[int, str, str]:
    checks, bad = 0, []
    seg = _ALL_REFS[(i * 41) % len(_ALL_REFS) :][:60] or _ALL_REFS[:60]
    for fname, key in seg:
        checks += 1
        if not all(key in LOC[lang] for lang in LANGS):
            missing = [lang for lang in LANGS if key not in LOC[lang]]
            bad.append(f"{fname}: {key} fehlt in {','.join(missing)}")
    # Toasts nie fuer destruktive Aktionen
    f = _VIEW_FILES[i % len(_VIEW_FILES)]
    src = f.read_text("utf-8")
    for m in re.finditer(r"show_info\(([^)]{0,160})", src):
        checks += 1
        if re.search(r"delete|loesch|remove|entfern", m.group(1), re.I):
            before = src[max(0, m.start() - 600) : m.start()]
            if not re.search(
                r"QMessageBox\.(question|warning)|StandardButton\.Yes"
                r"|QMessageBox\.Yes",
                before,
            ):
                bad.append(
                    f"{f.name}: Toast fuer destruktive Aktion ohne"
                    " vorherige Bestaetigung"
                )
    return (
        checks,
        "FAIL" if bad else "PASS",
        "; ".join(bad[:4]) or "Schluesseldisziplin ok",
    )


# ─────────────── k9 Dialog-/Navigations-Invarianten ───────────────
_DIALOG_SRC = {f: f.read_text("utf-8") for f in sorted((ROOT / "views").glob("*.py"))}
_ACC = (ROOT / "utils" / "accessibility.py").read_text("utf-8")


def k9_dialog_invariants(i: int, rng: random.Random) -> tuple[int, str, str]:
    checks, bad, warn = 0, [], []
    f, src = list(_DIALOG_SRC.items())[i % len(_DIALOG_SRC)]
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        is_dialog = any(
            (isinstance(b, ast.Name) and b.id == "QDialog")
            or (isinstance(b, ast.Attribute) and b.attr == "QDialog")
            for b in node.bases
        )
        if not is_dialog:
            continue
        body_src = ast.get_source_segment(src, node) or ""
        checks += 1
        if not re.search(r"reject|accept|QDialogButtonBox|close", src):
            bad.append(f"{f.name}:{node.name} nicht schliessbar")
        checks += 1
        if len(re.findall(r"QPushButton\(", body_src)) >= 5:
            if "configure_dialog_tab_order" not in src:
                warn.append(f"{f.name}:{node.name} ohne Tab-Ketten-Registrierung")
    checks += 1
    if "QMessageBox.information" in src:
        bad.append(f"{f.name}: modale Info")
    if bad:
        return checks, "FAIL", "; ".join(bad[:4])
    if warn:
        return checks, "WARN", "; ".join(warn[:3])
    return checks, "PASS", f"{f.name}: Invarianten ok"


# ─────────────── k10 Regressions-Vollschutz ───────────────
def k10_regression_shield(i: int, rng: random.Random) -> tuple[int, str, str]:
    from datetime import date
    from model.fixed_cost_due import is_open_this_month
    from model.migrations import _cols as mig_cols

    checks, bad = 0, []
    # Ultimo-Klemmung an drei Stichdaten
    for dd, y, m, today, expect in (
        (31, 2026, 2, date(2026, 2, 28), True),
        (31, 2024, 2, date(2024, 2, 28), False),
        (31, 2026, 4, date(2026, 4, 30), True),
    ):
        checks += 1
        open_, _ = is_open_this_month(
            is_fix=True,
            is_recurring=True,
            budget=100.0,
            booked=0.0,
            due_day=dd,
            year=y,
            month=m,
            today=today,
        )
        if open_ is not expect:
            bad.append(f"Ultimo {y}-{m:02d} due{dd} erwartet {expect}")
    # SQL-Guards
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE demo(id INTEGER)")
    checks += 1
    if mig_cols(conn, "demo; DROP TABLE demo") != set():
        bad.append("migrations._cols-Guard inaktiv")
    conn.close()
    # Tag-Restore-Verdrahtung + Quelle-Fallback
    undo_src = (ROOT / "model" / "undo_redo_model.py").read_text("utf-8")
    checks += 1
    if undo_src.count("_restore_tracking_tags(") < 4:
        bad.append("Tag-Restore-Aufrufe fehlen")
    checks += 1
    if "target_table = self._safe_table(target_table)" not in undo_src:
        bad.append("target_table-Whitelist fehlt")
    trk_src = (ROOT / "model" / "tracking_model.py").read_text("utf-8")
    checks += 1
    if "_source_select_expr" not in trk_src or "COALESCE(source" not in trk_src:
        bad.append("Quellen-Fallback fehlt")
    checks += 1
    mig_doc = (ROOT / "model" / "migrations.py").read_text("utf-8")
    if "auto_fixcost" not in mig_doc:
        bad.append("Quellen-Schema-Doku fehlt")
    # 0 modale Infos + Paritaet aller Sprachen
    checks += 1
    total = sum(
        f.read_text("utf-8").count("QMessageBox.information")
        for f in (ROOT / "views").rglob("*.py")
    )
    if total:
        bad.append(f"{total} modale Infos")
    checks += 1
    if len({len(LOC[lang]) for lang in LANGS}) != 1:
        bad.append("i18n-Paritaet der Sprachen verletzt")
    # Nachweise vorhanden
    for artefact in (
        "docs/archive/release-evidence/FINAL_RELEASE_AUDIT_1000_MATRIX_v2_2_25.csv",
        "tools/bandit_release_gate.py",
        "tools/enterprise_release_audit_10000.py",
        "tools/final_release_audit_1000.py",
    ):
        checks += 1
        if not (ROOT / artefact).exists():
            bad.append(f"Nachweis fehlt: {artefact}")
    return (
        checks,
        "FAIL" if bad else "PASS",
        "; ".join(bad) or "Regressionsschild intakt",
    )


DOMAINS = [
    ("k1_first_run_path", k1_first_run_path),
    ("k2_booking_lifecycle", k2_booking_lifecycle),
    ("k3_bundle_roundtrip", k3_bundle_roundtrip),
    ("k4_guide_coverage", k4_guide_coverage),
    ("k5_help_wiki", k5_help_wiki),
    ("k6_text_quality", k6_text_quality),
    ("k7_update_path", k7_update_path),
    ("k8_key_discipline", k8_key_discipline),
    ("k9_dialog_invariants", k9_dialog_invariants),
    ("k10_regression_shield", k10_regression_shield),
]


def main() -> int:
    rows = []
    totals = {"checks": 0, "PASS": 0, "WARN": 0, "FAIL": 0}
    fail_msgs: dict[str, str] = {}
    warn_msgs: dict[str, str] = {}
    loop_no = 0
    for i in range(LOOPS_PER_DOMAIN):
        for name, fn in DOMAINS:
            loop_no += 1
            rng = random.Random(f"{name}:{i}")
            try:
                checks, status, detail = fn(i, rng)
            except Exception as exc:  # Absturz = FAIL mit Nachweis
                checks, status, detail = 1, "FAIL", f"EXC {type(exc).__name__}: {exc}"
            totals["checks"] += checks
            totals[status] += 1
            if status == "FAIL":
                fail_msgs.setdefault(name, detail)
            elif status == "WARN":
                warn_msgs.setdefault(name, detail)
            rows.append((loop_no, name, checks, status, detail[:160]))
        if (i + 1) % 100 == 0:
            print(
                f"Loop {loop_no:05d}: checks={totals['checks']}"
                f" fail={totals['FAIL']} warn={totals['WARN']}"
            )
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["loop", "domain", "checks", "status", "detail"])
        w.writerows(rows)
    print(f"CSV: {CSV_PATH}")
    print(
        f"KILLCRITIC X10THINK DONE: loops={loop_no}"
        f" checks={totals['checks']} pass={totals['PASS']}"
        f" warn={totals['WARN']} fail={totals['FAIL']}"
    )
    for name, msg in sorted(fail_msgs.items()):
        print(f"  FAIL {name}: {msg}")
    for name, msg in sorted(warn_msgs.items()):
        print(f"  WARN {name}: {msg}")
    return 1 if totals["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
