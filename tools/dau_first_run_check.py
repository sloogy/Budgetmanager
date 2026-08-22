"""DAU End-to-End: simuliert den kompletten Ablauf NACH dem ersten Start
auf Logik-Ebene (ohne GUI). Prüft, ob ein ahnungsloser Nutzer ohne Fehler
durchkommt und die Daten danach konsistent sind.
"""

import os
import sys
import tempfile
import traceback

sys.path.insert(0, ".")

FAIL = []


def check(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        FAIL.append(msg)


print("=" * 64)
print("DAU E2E – Erststart-Durchführung (headless)")
print("=" * 64)

# --- Schritt 0: Sprache/Währung/Zahlenformat wie im LanguageSelectDialog ---
print("\n[0] Regionseinstellungen (DAU wählt: Deutsch, CHF, Format 'ch')")
import utils.i18n as i18n
import utils.money as money

i18n.set_language("de")
money.set_currency("CHF")
money.set_number_format("ch")
check(
    money.format_money(1234.5) == "1'234.50 CHF",
    f"Format CHF/ch: {money.format_money(1234.5)!r}",
)
# DAU mit deutschem Euro-Format
money.set_currency("EUR")
money.set_number_format("eu")
check(
    money.format_money(1234.5) == "1.234,50 €",
    f"Format EUR/eu: {money.format_money(1234.5)!r}",
)
money.set_currency("CHF")
money.set_number_format("ch")

# --- Schritt 1: Konto anlegen (StartupWizard → UserModel) ---
print("\n[1] Konto anlegen (Quick-Modus, kein Passwort)")
tmpdir = tempfile.mkdtemp()
os.environ["BUDGETMANAGER_APP_DIR"] = tmpdir
os.environ["HOME"] = tmpdir
try:
    from model.user_model import SECURITY_QUICK, UserModel

    um = UserModel()
    had_users_before = um.has_users()
    user, restore_key = um.create_user("Max Mustermann", SECURITY_QUICK, "")
    check(user is not None, "Quick-User angelegt")
    check(um.has_users(), "has_users() == True nach Anlage")
except Exception as e:
    check(False, f"User-Anlage Exception: {e}")
    traceback.print_exc()

# --- Schritt 2: DB anlegen + migrieren + Default-Kategorien (Setup-Assistent) ---
print("\n[2] DB anlegen, migrieren, Default-Kategorien laden")
from model.budget_model import BudgetModel
from model.category_model import CategoryModel
from model.database import open_db
from model.migrations import migrate_all
from model.tracking_model import TrackingModel

db_path = os.path.join(tmpdir, "budgetmanager.db")
conn = open_db(db_path)
info = migrate_all(conn, db_path, tmpdir)
check(conn is not None, "DB geöffnet")
cats = CategoryModel(conn)
cats.ensure_defaults()
all_cats = cats.list()
check(len(all_cats) > 0, f"Default-Kategorien geladen: {len(all_cats)} Stück")
tree = cats.build_tree(all_cats)
check(
    isinstance(tree, list) and len(tree) > 0,
    f"Kategorien-Baum baubar ({len(tree)} Wurzeln)",
)
# Gibt es Haupt- mit Unterkategorien?
has_children = any(c.parent_id is not None for c in all_cats)
check(has_children, "Mindestens eine Unterkategorie vorhanden (Hierarchie)")

# --- Schritt 3: Budget-Starter (DAU trägt Werte ein) ---
print("\n[3] Budget-Werte eintragen (Setup-Schritt 'Budget')")
bud = BudgetModel(conn)
sample = all_cats[0]
try:
    bud.set_amount(2026, 1, sample.typ, sample.name, 1234.50)
    val = conn.execute(
        "SELECT amount FROM budget WHERE year=2026 AND month=1 AND typ=? AND category=?",
        (sample.typ, sample.name),
    ).fetchone()[0]
    check(abs(val - 1234.50) < 1e-6, f"Budget gesetzt für '{sample.name}': {val}")
except Exception as e:
    check(False, f"Budget set_amount Exception: {e}")

# --- Schritt 4: Tracking-Testbuchung ---
print("\n[4] Testbuchung erfassen (Setup-Schritt 'Tracking')")
trk = TrackingModel(conn)
try:
    trk.add("2026-01-15", sample.typ, sample.name, 49.50, "DAU Testbuchung")
    cnt = conn.execute(
        "SELECT COUNT(*) FROM tracking WHERE category=?", (sample.name,)
    ).fetchone()[0]
    check(cnt == 1, f"Buchung erfasst (count={cnt})")
except Exception as e:
    check(False, f"Tracking add Exception: {e}")

# --- Schritt 5: DAU benennt eine Kategorie um → muss überall mitwandern ---
print("\n[5] Kategorie umbenennen (Cascade über alle Tabellen)")
try:
    cats.rename_and_cascade(
        sample.id, typ=sample.typ, old_name=sample.name, new_name="DAU-Umbenannt"
    )
    b = conn.execute(
        "SELECT COUNT(*) FROM budget WHERE category='DAU-Umbenannt'"
    ).fetchone()[0]
    t = conn.execute(
        "SELECT COUNT(*) FROM tracking WHERE category='DAU-Umbenannt'"
    ).fetchone()[0]
    rest = conn.execute(
        "SELECT COUNT(*) FROM budget WHERE category=?", (sample.name,)
    ).fetchone()[0]
    check(
        b == 1 and t == 1 and rest == 0,
        f"Rename-Cascade ok (budget={b}, tracking={t}, Reste={rest})",
    )
except Exception as e:
    check(False, f"Rename Exception: {e}")

# --- Schritt 6: DAU löscht eine Hauptkategorie mit Kindern (Promotion) ---
print("\n[6] Hauptkategorie mit Kindern löschen → Kinder werden hochgestuft")
try:
    parent = next(
        (c for c in cats.list() if any(ch.parent_id == c.id for ch in cats.list())),
        None,
    )
    if parent:
        child_ids_before = [c.id for c in cats.list() if c.parent_id == parent.id]
        cats.delete_category_safely(
            parent.id, data_action="delete_until_last_booking", promote_children=True
        )
        promoted = [cats.get_by_id(cid) for cid in child_ids_before]
        ok = all(c is not None and c.parent_id is None for c in promoted)
        check(ok, f"{len(child_ids_before)} Kinder zu Hauptkategorien hochgestuft")
    else:
        check(True, "Keine Parent-mit-Kindern im Default-Set (übersprungen)")
except Exception as e:
    check(False, f"Delete/Promotion Exception: {e}")

# --- Schritt 7: Integrität – keine verwaisten Referenzen ---
print("\n[7] Integritätsprüfung – keine verwaisten Kategorie-Referenzen")
try:
    cat_names = {(c.typ, c.name) for c in cats.list()}
    orphans = 0
    for table in (
        "budget",
        "tracking",
        "budget_warnings",
        "favorites",
        "recurring_transactions",
        "suggestion_accepted",
    ):
        for r in conn.execute(
            f"SELECT DISTINCT typ, category FROM {table}"  # nosec B608
        ).fetchall():
            if (r[0], r[1]) not in cat_names:
                orphans += 1
    # verwaiste parent_id?
    valid_ids = {c.id for c in cats.list()}
    dangling = conn.execute(
        "SELECT COUNT(*) FROM categories WHERE parent_id IS NOT NULL "
        f"AND parent_id NOT IN ({','.join(str(i) for i in valid_ids or [0])})"  # nosec B608
    ).fetchone()[0]
    check(orphans == 0, f"Keine verwaisten Namens-Referenzen (gefunden: {orphans})")
    check(dangling == 0, f"Keine hängenden parent_id (gefunden: {dangling})")
except Exception as e:
    check(False, f"Integritäts-Check Exception: {e}")

conn.close()

# --- Schritt 8: DAU-Fehleingaben werden fail-closed abgewiesen (v2.2.32) ---
print("\n[8] Fehleingabe-Robustheit – inf/nan gelangen nie in die Datenbank")
try:
    import math as _math
    import sqlite3 as _sqlite3
    from datetime import date as _date

    from model.budget_model import BudgetModel
    from model.savings_goals_model import (
        SavingsGoalBoundsError,
        SavingsGoalsModel,
    )
    from model.tracking_model import TrackingModel
    from model.typ_constants import TYP_EXPENSES as _TYP_EXP
    from utils.money import parse_money

    # 8a: parse_money weist nicht-endliche Eingaben ab (fail-closed)
    rejected = 0
    for bad in ("inf", "Infinity", "nan", "1e400", "9" * 400):
        try:
            parse_money(bad)
        except ValueError:
            rejected += 1
    check(
        rejected == 5,
        f"parse_money weist inf/nan/Overflow ab ({rejected}/5)",
    )

    # 8b: gültige Beträge funktionieren weiterhin
    good_ok = all(
        abs(parse_money(v) - exp) < 1e-9
        for v, exp in (("1,50", 1.5), ("1.234,56", 1234.56), ("-5", -5.0))
    )
    check(good_ok, "Gültige Beträge werden weiterhin korrekt geparst")

    # 8c: DB-Schreibgrenze lehnt inf/nan ab (Budget + Tracking + Sparziel)
    _c2 = _sqlite3.connect(":memory:")
    _c2.row_factory = _sqlite3.Row
    from model.migrations import migrate_all as _mig

    _mig(_c2)
    _bm = BudgetModel(_c2)
    _tm = TrackingModel(_c2)
    _sm = SavingsGoalsModel(_c2)
    db_rejects = 0
    for bad in (float("inf"), float("nan")):
        try:
            _bm.set_amount(2026, 7, _TYP_EXP, "Miete", bad)
        except ValueError:
            db_rejects += 1
        try:
            _tm.add(_date(2026, 7, 1), _TYP_EXP, "Miete", bad, "x")
        except ValueError:
            db_rejects += 1
        try:
            _sm.create(name="T", target_amount=bad, current_amount=0)
        except SavingsGoalBoundsError:
            db_rejects += 1
    check(
        db_rejects == 6, f"Budget/Tracking/Sparziel weisen inf/nan ab ({db_rejects}/6)"
    )

    # 8d: nach den Fehlversuchen steht kein einziger nicht-endlicher Betrag in der DB
    non_finite = 0
    for tbl, col in (
        ("budget", "amount"),
        ("tracking", "amount"),
        ("savings_goals", "target_amount"),
        ("savings_goals", "current_amount"),
    ):
        for r in _c2.execute(f"SELECT {col} FROM {tbl}").fetchall():  # nosec B608
            v = r[0]
            if v is not None and not _math.isfinite(float(v)):
                non_finite += 1
    check(
        non_finite == 0,
        f"Keine nicht-endlichen Beträge in der DB (gefunden: {non_finite})",
    )
    _c2.close()
except Exception as e:
    check(False, f"Fehleingabe-Robustheit Exception: {e}")

print("\n" + "=" * 64)
print(
    f"ERGEBNIS: {'ALLE CHECKS BESTANDEN ✅' if not FAIL else f'{len(FAIL)} FEHLER ❌'}"
)
for f in FAIL:
    print("   -", f)
print("=" * 64)
sys.exit(1 if FAIL else 0)
