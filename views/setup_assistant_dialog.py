from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QPushButton, QCheckBox, QRadioButton, QButtonGroup, QGroupBox,
    QFileDialog, QMessageBox, QFrame
)

from views.category_excel_io import export_category_template_xlsx, import_categories_from_xlsx
from views.budget_fill_dialog import BudgetFillDialog
from model.category_model import CategoryModel
from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel
from utils.i18n import tr, trf, display_typ, db_typ_from_display


@dataclass
class _Step:
    title: str
    widget: QWidget
    on_enter: callable | None = None
    is_blocking: bool = False  # wenn True: Next nur, wenn self._step_done[idx] True ist


class SetupAssistantDialog(QDialog):
    """Kurzer First-Start-Guide (nicht modal), der durch Setup & Kernfunktionen führt."""

    def __init__(
        self,
        main_window,
        conn: sqlite3.Connection,
        settings,
        *,
        db_existed_before: bool,
    ):
        super().__init__(main_window)
        self.main_window = main_window
        self.conn = conn
        self.settings = settings
        self.db_path = Path(self.settings.get("database_path", "budgetmanager.db")).expanduser()
        self.db_existed_before = bool(db_existed_before)
        self._cat_model = CategoryModel(conn)
        self._budget_model = BudgetModel(conn)
        self._tracking_model = TrackingModel(conn)

        self._cats_done = False
        self._budget_done = False
        self._budget_opened_once = False
        self._budget_done = False

        self.setWindowTitle(tr("dlg.setup_assistant"))
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)

        root = QVBoxLayout(self)

        self.lbl_header = QLabel()
        self.lbl_header.setWordWrap(True)
        self.lbl_header.setTextFormat(Qt.RichText)

        self.stack = QStackedWidget()

        nav = QHBoxLayout()
        self.btn_back = QPushButton(tr("setup.zurueck"))
        self.btn_next = QPushButton("Weiter →")
        self.btn_finish = QPushButton("Fertig")
        self.btn_finish.setVisible(False)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_finish.clicked.connect(self._finish)

        nav.addWidget(self.btn_back)
        nav.addStretch(1)
        nav.addWidget(self.btn_next)
        nav.addWidget(self.btn_finish)

        root.addWidget(self.lbl_header)
        root.addWidget(self._hline())
        root.addWidget(self.stack, 1)
        root.addWidget(self._hline())
        root.addLayout(nav)

        # Steps
        self.steps: list[_Step] = []
        self._step_done: list[bool] = []

        self._build_steps()

        for st in self.steps:
            self.stack.addWidget(st.widget)

        self._set_step(0)

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def _hline(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def _mk_page(self, title: str, body_html: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        t = QLabel(f"<h3>{title}</h3>")
        t.setTextFormat(Qt.RichText)
        lay.addWidget(t)

        b = QLabel(body_html)
        b.setTextFormat(Qt.RichText)
        b.setWordWrap(True)
        lay.addWidget(b)
        lay.addStretch(1)
        return w

    # ---------------------------------------------------------------------
    # Build pages
    # ---------------------------------------------------------------------
    def _build_steps(self) -> None:
        self._build_step_mode()
        self._build_step_db()
        self._build_step_cat_method()
        self._build_step_cat_manager()
        self._build_step_cat_excel()
        self._build_step_budget_load()
        self._build_step_budget_explain()
        self._build_step_tracking_first()
        self._build_step_tracking_fix()
        self._build_step_finish()

        self._step_done = [False] * len(self.steps)
        for i, st in enumerate(self.steps):
            self._step_done[i] = not st.is_blocking

    # ── Step-Builder ─────────────────────────────────────────────

    def _build_step_mode(self) -> None:
        """1) Guided vs. unguided."""
        self.page_mode = QWidget()
        lay = QVBoxLayout(self.page_mode)
        lay.addWidget(QLabel("<h3>" + tr("setup.setup_mode_title") + "</h3>"))
        info = QLabel(tr("setup.setup_mode_intro"))
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        lay.addWidget(info)
        self.cb_guided = QCheckBox(tr("chk.guided_setup"))
        self.cb_guided.setChecked(True)
        self.cb_show_on_start = QCheckBox(tr("chk.show_onboarding"))
        self.cb_show_on_start.setChecked(bool(self.settings.get("show_onboarding", True)))
        lay.addWidget(self.cb_guided)
        lay.addWidget(self.cb_show_on_start)
        lay.addStretch(1)
        self.steps.append(_Step("Startmodus", self.page_mode))

    def _build_step_db(self) -> None:
        """2) Datenbank-Check."""
        self.page_db = QWidget()
        lay = QVBoxLayout(self.page_db)
        lay.addWidget(QLabel("<h3>2) Datenbank-Check</h3>"))
        exists_txt = tr("setup.setup_db_exists") if self.db_existed_before else tr("setup.setup_db_not_exists")
        self.lbl_db = QLabel(
            f"<b>{tr('setup.setup_db_path')}:</b> {self.db_path}<br>"
            f"<b>{tr('setup.setup_db_existed')}:</b> {exists_txt}<br><br>"
            + tr("setup.setup_db_desc")
        )
        self.lbl_db.setTextFormat(Qt.RichText)
        self.lbl_db.setWordWrap(True)
        lay.addWidget(self.lbl_db)
        
        # Restore + Reset buttons
        from PySide6.QtWidgets import QPushButton, QHBoxLayout
        btn_row = QHBoxLayout()
        btn_restore = QPushButton("💾 " + tr("setup.setup_db_restore"))
        btn_restore.clicked.connect(self._do_restore_backup)
        btn_reset = QPushButton("🗑️ " + tr("setup.setup_db_reset"))
        btn_reset.clicked.connect(self._do_reset_database)
        btn_row.addWidget(btn_restore)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.setup_db_title"), self.page_db))

    def _build_step_cat_method(self) -> None:
        """3) Kategorien-Methode wählen."""
        self.page_cat_method = QWidget()
        lay = QVBoxLayout(self.page_cat_method)
        lay.addWidget(QLabel("<h3>3) Kategorien anlegen</h3>"))
        try:
            cnt = self._cat_model.count()
        except Exception:
            cnt = 0
        hint = QLabel(
            "Du kannst Kategorien direkt im <b>Kategorien-Manager</b> erstellen, oder über eine <b>Excel-Vorlage</b> importieren."
            "<br><small>Beispiel-Pfad: Gesundheit \u203a Krankenkasse \u203a Prämie</small>"
        )
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        lay.addWidget(hint)
        gb = QGroupBox("Methode")
        vb = QVBoxLayout(gb)
        self.rb_cat_manager = QRadioButton(tr("radio.cat_manager"))
        self.rb_cat_excel = QRadioButton(tr("radio.cat_excel"))
        self.rb_cat_manager.setChecked(True)
        vb.addWidget(self.rb_cat_manager)
        vb.addWidget(self.rb_cat_excel)
        lay.addWidget(gb)
        self.cb_clean_start = QCheckBox(trf("setup.clean_start_vorhandene_kategorien"))
        allow_clean = self._is_safe_to_reset()
        self.cb_clean_start.setEnabled(bool(allow_clean and cnt > 0))
        if not allow_clean and cnt > 0:
            self.cb_clean_start.setToolTip(tr("setup.dein_budgettracking_enthaelt_bereits"))
        lay.addWidget(self.cb_clean_start)
        lay.addStretch(1)
        self.steps.append(_Step("Kategorien Methode", self.page_cat_method))

    def _build_step_cat_manager(self) -> None:
        """4.1) Kategorien-Manager."""
        self.page_cat_manager = QWidget()
        lay = QVBoxLayout(self.page_cat_manager)
        lay.addWidget(QLabel("<h3>4) Kategorien-Manager</h3>"))
        desc = QLabel(tr("setup.klicke_auf_boeffnenb_lege"))
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_open_cat_manager = QPushButton(tr("setup.open_cat_manager"))
        self.btn_open_cat_manager.clicked.connect(self._open_category_manager)
        lay.addWidget(self.btn_open_cat_manager)
        self.lbl_cat_done_1 = QLabel(tr("setup.smallnoch_nicht_abgeschlossensmall"))
        self.lbl_cat_done_1.setTextFormat(Qt.RichText)
        self.lbl_cat_done_1.setWordWrap(True)
        lay.addWidget(self.lbl_cat_done_1)
        lay.addStretch(1)
        self.steps.append(_Step(tr("dlg.category_manager"), self.page_cat_manager, is_blocking=True))

    def _build_step_cat_excel(self) -> None:
        """4.2) Excel-Import."""
        self.page_cat_excel = QWidget()
        lay = QVBoxLayout(self.page_cat_excel)
        lay.addWidget(QLabel("<h3>4) Excel-Import</h3>"))
        desc = QLabel(
            "1) Exportiere eine Excel-Vorlage, fülle sie aus, und importiere sie dann wieder.<br>"
            "2) Danach öffnet sich zur Kontrolle automatisch der Kategorien-Manager."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_export_template = QPushButton(tr("setup.export_template"))
        self.btn_export_template.clicked.connect(self._export_template)
        lay.addWidget(self.btn_export_template)
        self.btn_import_template = QPushButton(tr("setup.import_template"))
        self.btn_import_template.clicked.connect(self._import_from_excel)
        lay.addWidget(self.btn_import_template)
        self.lbl_cat_done_2 = QLabel(tr("setup.smallnoch_nicht_abgeschlossensmall"))
        self.lbl_cat_done_2.setTextFormat(Qt.RichText)
        self.lbl_cat_done_2.setWordWrap(True)
        lay.addWidget(self.lbl_cat_done_2)
        lay.addStretch(1)
        self.steps.append(_Step("Excel-Import", self.page_cat_excel, is_blocking=True))

    def _build_step_budget_load(self) -> None:
        """5) Budget-Fenster öffnen."""
        self.page_budget_load = QWidget()
        lay = QVBoxLayout(self.page_budget_load)
        lay.addWidget(QLabel(tr("setup.h35_budget_ausfuellenh3")))
        desc = QLabel(
            "Der Budget-Tab wird jetzt als <b>eigenes Fenster</b> geöffnet, damit du ihn direkt ausfüllen kannst.<br><br>"
            "• Kategorien werden aus der Datenbank geladen.<br>"
            "• Du trägst Monatswerte in die Tabelle ein.<br>"
            "• Danach schließt du das Budget-Fenster und klickst hier auf <b>Weiter</b>."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_open_budget_window = QPushButton(tr("setup.open_budget_window"))
        self.btn_open_budget_window.clicked.connect(self._open_budget_window)
        lay.addWidget(self.btn_open_budget_window)
        self.lbl_budget_done = QLabel(tr("setup.smallnoch_nicht_geoeffnetsmall"))
        self.lbl_budget_done.setTextFormat(Qt.RichText)
        self.lbl_budget_done.setWordWrap(True)
        lay.addWidget(self.lbl_budget_done)
        lay.addStretch(1)
        self.steps.append(_Step(tr("setup.budget_ausfuellen"), self.page_budget_load,
                                on_enter=self._enter_budget_tab_and_open_budget_window_once, is_blocking=True))

    def _build_step_budget_explain(self) -> None:
        """6) Budget-Tab Erklärung."""
        self.page_budget_explain = self._mk_page(
            tr("setup.step6_title"),
            "<b>6.1 Kategorien bearbeiten</b><br>"
            "• Rechtsklick auf eine Zeile (oder ⚙/Dialog) → Umbenennen, Löschen, Flags setzen.<br><br>"
            "<b>6.2 Budget setzen</b><br>"
            "• In den Monatsspalten direkt Beträge in der gewählten Währung eintragen.<br>"
            "• Total wird automatisch berechnet.<br><br>"
            "<b>6.3 Tabelle erklärt</b><br>"
            "• Spalte <b>⭐ Fix</b>: Fixkosten markieren (z. B. Miete).<br>"
            "• Spalte <b>∞ Wiederkehrend</b>: wiederkehrende Buchung (z. B. Monatsabo).<br>"
            "• Spalte <b>Tag</b>: Fälligkeitstag im Monat (1–31)."
        )
        self.steps.append(_Step(tr("setup.budget_erklaerung"), self.page_budget_explain, on_enter=self._enter_budget_tab))

    def _build_step_tracking_first(self) -> None:
        """7) Tracking — erste Buchung."""
        self.page_tracking_first = QWidget()
        lay = QVBoxLayout(self.page_tracking_first)
        lay.addWidget(QLabel("<h3>7) Tracking – erste Buchung</h3>"))
        desc = QLabel(
            "Im <b>Tracking</b> (Buchungen) erfasst du echte Zahlungen.<br>"
            "Klicke auf <b>Erste Buchung hinzufügen</b> und speichere – oder überspringe den Test."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_add_first = QPushButton(tr("setup.add_first_booking"))
        self.btn_add_first.clicked.connect(self._open_first_booking)
        lay.addWidget(self.btn_add_first)
        lay.addStretch(1)
        self.steps.append(_Step("Tracking erste Buchung", self.page_tracking_first, on_enter=self._enter_tracking_tab))

    def _build_step_tracking_fix(self) -> None:
        """8) Tracking — Fixkosten / Wiederkehrend."""
        self.page_tracking_fix = QWidget()
        lay = QVBoxLayout(self.page_tracking_fix)
        lay.addWidget(QLabel("<h3>8) Tracking – Fixkosten / Wiederkehrend</h3>"))
        desc = QLabel(
            "<b>8.1 Fix/Wiederkehrend buchen</b><br>"
            "Der Button <b>Fix/Wiederkehrend buchen…</b> erstellt Buchungen aus Kategorien, "
            "die als ⭐ Fixkosten oder ∞ Wiederkehrend markiert sind.<br><br>"
            "<b>Was passiert?</b><br>"
            "• Es wird eine Liste vorbereitet.<br>"
            "• Fixkosten übernehmen den Betrag aus dem Budget (wenn > 0).<br>"
            "• Wiederkehrende (ohne Fixbetrag) können im Dialog angepasst werden."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)
        self.btn_open_fix = QPushButton(tr("setup.book_fixcosts"))
        self.btn_open_fix.clicked.connect(self._open_fix_dialog)
        lay.addWidget(self.btn_open_fix)
        lay.addStretch(1)
        self.steps.append(_Step("Tracking Fix", self.page_tracking_fix, on_enter=self._enter_tracking_tab))

    def _build_step_finish(self) -> None:
        """Abschluss-Seite."""
        self.page_finish = QWidget()
        lay = QVBoxLayout(self.page_finish)
        lay.addWidget(QLabel("<h3>Fertig ✅</h3>"))
        done = QLabel(
            "Du hast den Quick-Guide abgeschlossen.<br><br>"
            "Tipps:<br>"
            "• Kategorien-Pfad hilft überall (z. B. Gesundheit \u203a Krankenkasse \u203a Prämie).<br>"
            "• Budget = Plan, Tracking = Realität.<br>"
            "• Dashboard/Übersicht vergleicht Budget vs. Getracked."
        )
        done.setTextFormat(Qt.RichText)
        done.setWordWrap(True)
        lay.addWidget(done)
        self.cb_show_on_start_end = QCheckBox(tr("chk.show_onboarding_end"))
        self.cb_show_on_start_end.setChecked(False)
        lay.addWidget(self.cb_show_on_start_end)
        lay.addStretch(1)
        self.steps.append(_Step("Fertig", self.page_finish))

    # ---------------------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------------------
    def _set_step(self, idx: int) -> None:
        idx = max(0, min(idx, len(self.steps) - 1))
        self.stack.setCurrentIndex(idx)
        st = self.steps[idx]
        self.lbl_header.setText(f"<b>{st.title}</b> ({idx+1}/{len(self.steps)})")
        if st.on_enter:
            try:
                st.on_enter()
            except Exception as e:
                logger.debug("%s", e)
                # Wizard must not crash UI
                pass
        self._update_nav()

    def _current_idx(self) -> int:
        return int(self.stack.currentIndex())

    def _update_nav(self) -> None:
        idx = self._current_idx()
        self.btn_back.setEnabled(idx > 0)
        last = idx == (len(self.steps) - 1)
        self.btn_next.setVisible(not last)
        self.btn_finish.setVisible(last)

        # Next enabled?
        can_next = True
        # page 0: if unguided, allow Next (will finish)
        if idx == 0:
            can_next = True
        else:
            can_next = bool(self._step_done[idx])
        self.btn_next.setEnabled(can_next)

    def _go_back(self) -> None:
        idx = self._current_idx()

        # handle branching back: from cat manager/excel to method page
        if idx in (3, 4):
            self._set_step(2)
            return

        self._set_step(idx - 1)

    def _go_next(self) -> None:
        idx = self._current_idx()

        # page 0: unguided -> close
        if idx == 0 and not self.cb_guided.isChecked():
            self.settings.set("show_onboarding", bool(self.cb_show_on_start.isChecked()))
            self.settings.set("setup_completed", True)
            self.close()
            return

        # page 2 -> branch
        if idx == 2:
            if self.cb_clean_start.isChecked():
                self._reset_categories()
            self._set_step(4 if self.rb_cat_excel.isChecked() else 3)
            return

        # after cat pages -> budget load
        if idx in (3, 4):
            self._set_step(5)
            return

        self._set_step(idx + 1)

    def _finish(self) -> None:
        # mark completed and apply "show on start"
        self.settings.set("show_onboarding", bool(self.cb_show_on_start_end.isChecked()))
        self.settings.set("setup_completed", True)
        QMessageBox.information(self, "OK", "Setup-Assistent abgeschlossen.")
        self.close()


    def closeEvent(self, event):  # noqa: N802 (Qt naming)
        """Beim Schließen: Einstellung tr("chk.show_onboarding") persistieren.

        Wichtig:
        - Nicht automatisch als abgeschlossen markieren (setup_completed bleibt False),
          außer der User hat aktiv 'Fertig' geklickt.
        """
        try:
            if hasattr(self, "cb_show_on_start_end") and self.stack.currentWidget() is self.page_finish:
                self.settings.set("show_onboarding", bool(self.cb_show_on_start_end.isChecked()))
            elif hasattr(self, "cb_show_on_start"):
                self.settings.set("show_onboarding", bool(self.cb_show_on_start.isChecked()))
        except Exception as e:
            logger.debug("if hasattr(self, 'cb_show_on_start_end') and self.: %s", e)
        return super().closeEvent(event)

    # ---------------------------------------------------------------------
    # Enter hooks
    # ---------------------------------------------------------------------
    def _enter_budget_tab(self) -> None:
        try:
            if hasattr(self.main_window, "_goto_tab"):
                self.main_window._goto_tab(self.main_window.budget_tab)
            else:
                self.main_window.tabs.setCurrentWidget(self.main_window.budget_tab)
            # reload view
            if hasattr(self.main_window.budget_tab, "load"):
                self.main_window.budget_tab.load()
            elif hasattr(self.main_window.budget_tab, "refresh"):
                self.main_window.budget_tab.refresh()
        except Exception as e:
            logger.debug("if hasattr(self.main_window, '_goto_tab'):: %s", e)

    def _enter_tracking_tab(self) -> None:
        try:
            if hasattr(self.main_window, "_goto_tab"):
                self.main_window._goto_tab(self.main_window.tracking_tab)
            else:
                self.main_window.tabs.setCurrentWidget(self.main_window.tracking_tab)
            if hasattr(self.main_window.tracking_tab, "refresh"):
                self.main_window.tracking_tab.refresh()
        except Exception as e:
            logger.debug("if hasattr(self.main_window, '_goto_tab'):: %s", e)

    # ---------------------------------------------------------------------
    # Actions (pages)
    # ---------------------------------------------------------------------
    def _open_category_manager(self) -> None:
        try:
            self.main_window._show_category_manager()
            # manager is modal; when it closes, consider done if there is at least one category
            cnt = self._cat_model.count()
            if cnt <= 0:
                QMessageBox.information(self, tr("msg.info"), "Noch keine Kategorien vorhanden. Du kannst trotzdem fortfahren.")
            self._cats_done = True
            self._step_done[3] = True
            self.lbl_cat_done_1.setText("<small>✅ Kategorien-Manager abgeschlossen.</small>")
            self._update_nav()
            self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_cat_manager_failed", e=e))

    def _export_template(self) -> None:
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                tr("setup.ordner_waehlen_excelvorlage_speichern"),
                str(Path.home()),
            )
            if not folder:
                return
            out = Path(folder) / "Budgetmanager_Kategorien_Template.xlsx"
            export_category_template_xlsx(out)
            QMessageBox.information(
                self,
                "OK",
                trf("msg.vorlage_gespeichert", out=out),
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Export fehlgeschlagen:\n{e}")

    def _import_from_excel(self) -> None:
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                tr("setup.kategorienexcel_auswaehlen"),
                str(Path.home()),
                "Excel (*.xlsx)",
            )
            if not file_path:
                return
            res = import_categories_from_xlsx(self.conn, Path(file_path))
            msg = (
                f"Import abgeschlossen.\n"
                f"Eingefügt: {res.inserted}\n"
                f"Aktualisiert: {res.updated}\n"
                f"Übersprungen: {res.skipped}"
            )
            if res.warnings:
                msg += "\n\nWarnungen:\n- " + "\n- ".join(res.warnings[:12])
                if len(res.warnings) > 12:
                    msg += f"\n… ({len(res.warnings)-12} weitere)"
            QMessageBox.information(self, "OK", msg)

            # Kontrolle im Kategorien-Manager
            QMessageBox.information(self, "Kontrolle", tr("setup.zur_kontrolle_oeffnet_sich"))
            self.main_window._show_category_manager()

            self._cats_done = True
            self._step_done[4] = True
            self.lbl_cat_done_2.setText("<small>✅ Excel-Import abgeschlossen.</small>")
            self._update_nav()
            self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Import fehlgeschlagen:\n{e}")

    def _open_first_booking(self) -> None:
        try:
            # tracking_tab.add() öffnet den Dialog und speichert bei OK
            if hasattr(self.main_window.tracking_tab, "add"):
                self.main_window.tracking_tab.add()
                self.main_window.tracking_tab.refresh()
            else:
                QMessageBox.information(self, tr("msg.info"), tr("msg.setup_tracking_unavailable"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_dialog_failed", e=e))

    def _open_fix_dialog(self) -> None:
        try:
            if hasattr(self.main_window.tracking_tab, "add_fixcosts"):
                self.main_window.tracking_tab.add_fixcosts()
            else:
                QMessageBox.information(self, tr("msg.info"), tr("msg.setup_fixrecurring_unavailable"))
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_dialog_failed", e=e))

    def _enter_budget_tab_and_open_budget_window_once(self) -> None:
        """Wechselt in den Budget-Tab und öffnet beim ersten Eintritt das Budget-Fenster."""
        self._enter_budget_tab()
        if not self._budget_opened_once:
            self._open_budget_window(auto=True)

    def _open_budget_window(self, *, auto: bool = False) -> None:
        """Öffnet ein separates Budget-Fenster zum direkten Ausfüllen."""
        try:
            dlg = BudgetFillDialog(self.main_window, self.conn, title=tr("setup.budget_ausfuellen_setup"))
            dlg.exec()

            self._budget_opened_once = True
            self._budget_done = True

            # Step-Index: 5 (nach Start/DB/Kat-Methode/Kat-Seiten)
            if len(self._step_done) > 5:
                self._step_done[5] = True

            if hasattr(self, "lbl_budget_done"):
                self.lbl_budget_done.setText(tr("setup.small_budgetfenster_wurde_geoeffnetsmall"))
            self._update_nav()

            # Tabs neu laden (Budget/Übersicht hängen davon ab)
            if hasattr(self.main_window, "_refresh_all_tabs"):
                self.main_window._refresh_all_tabs()
        except Exception as e:
            # Auto-Open soll UI nicht nerven – Button-Open darf Fehler zeigen
            if not auto:
                QMessageBox.critical(self, tr("msg.error"), trf("msg.setup_budget_window_failed", e=e))

    # ---------------------------------------------------------------------
    # Safety helpers
    # ---------------------------------------------------------------------

    def _do_restore_backup(self) -> None:
        """Backup wiederherstellen aus dem Setup-Assistenten."""
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getOpenFileName(
                self,
                tr("setup.setup_db_restore"),
                "",
                "Backup-Dateien (*.db *.sqlite *.bak *.zip);;Alle Dateien (*.*)"
            )
            if not path:
                return
            # Direkt über den Backup-Dialog öffnen
            from views.backup_restore_dialog import BackupRestoreDialog
            dlg = BackupRestoreDialog(self, self.conn, restore_path=path)
            dlg.exec()
            # DB-Info aktualisieren
            try:
                self.lbl_db.setText(
                    f"<b>{tr('setup.setup_db_path')}:</b> {self.db_path}<br>"
                    + tr("setup.setup_db_desc")
                )
            except Exception:
                pass
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, tr("msg.error"), str(e))

    def _do_reset_database(self) -> None:
        """Datenbank zurücksetzen aus dem Setup-Assistenten."""
        try:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                tr("setup.setup_db_reset"),
                tr("dlg.datenbank_reset_wirklich"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            # DB-Management Dialog öffnen
            from views.database_management_dialog import DatabaseManagementDialog
            dlg = DatabaseManagementDialog(self, self.conn, self.settings)
            dlg.exec()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, tr("msg.error"), str(e))

    def _is_safe_to_reset(self) -> bool:
        try:
            b = self._budget_model.count()
        except Exception:
            b = 0
        try:
            t = self._tracking_model.count()
        except Exception:
            t = 0
        # nur wenn Budget+Tracking leer sind
        return (b == 0 and t == 0)

    def _reset_categories(self) -> None:
        try:
            if not self._is_safe_to_reset():
                QMessageBox.warning(self, tr("setup.nicht_moeglich"), "Reset ist deaktiviert, weil bereits Daten vorhanden sind.")
                return
            if QMessageBox.question(
                self,
                "Clean Start",
                tr("setup.wirklich_alle_kategorien_loeschen"),
            ) != QMessageBox.Yes:
                self.cb_clean_start.setChecked(False)
                return

            self._cat_model.delete_all()
            self.conn.commit()
            QMessageBox.information(self, "OK", tr("setup.kategorien_wurden_geloescht"))
            self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Reset fehlgeschlagen:\n{e}")
