from __future__ import annotations

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

        self._cats_done = False
        self._budget_done = False
        self._budget_opened_once = False
        self._budget_done = False

        self.setWindowTitle("🧭 Erste Schritte – Setup-Assistent")
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setModal(False)

        root = QVBoxLayout(self)

        self.lbl_header = QLabel()
        self.lbl_header.setWordWrap(True)
        self.lbl_header.setTextFormat(Qt.RichText)

        self.stack = QStackedWidget()

        nav = QHBoxLayout()
        self.btn_back = QPushButton("← Zurück")
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
        # 1) Guided vs unguided
        self.page_mode = QWidget()
        lay = QVBoxLayout(self.page_mode)

        lay.addWidget(QLabel("<h3>1) Startmodus</h3>"))
        info = QLabel(
            "Möchtest du dich kurz durch das erste Setup führen lassen?<br>"
            "<small>Du kannst den Assistenten später jederzeit über <b>Hilfe → Erste Schritte</b> erneut starten.</small>"
        )
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        lay.addWidget(info)

        self.cb_guided = QCheckBox("Geführtes Setup starten (empfohlen)")
        self.cb_guided.setChecked(True)

        self.cb_show_on_start = QCheckBox("Einführung beim Start anzeigen")
        self.cb_show_on_start.setChecked(bool(self.settings.get("show_onboarding", True)))

        lay.addWidget(self.cb_guided)
        lay.addWidget(self.cb_show_on_start)
        lay.addStretch(1)

        self.steps.append(_Step("Startmodus", self.page_mode))

        # 2) DB check page
        self.page_db = QWidget()
        lay = QVBoxLayout(self.page_db)
        lay.addWidget(QLabel("<h3>2) Datenbank-Check</h3>"))

        exists_txt = "Ja" if self.db_existed_before else "Nein (wird/ wurde automatisch erstellt)"
        self.lbl_db = QLabel(
            f"<b>Pfad:</b> {self.db_path}<br>"
            f"<b>Vor dem Start vorhanden:</b> {exists_txt}<br><br>"
            "Der Budgetmanager speichert alles lokal in einer SQLite-Datenbank."
        )
        self.lbl_db.setTextFormat(Qt.RichText)
        self.lbl_db.setWordWrap(True)
        lay.addWidget(self.lbl_db)
        lay.addStretch(1)

        self.steps.append(_Step("DB", self.page_db))

        # 3) Category setup method
        self.page_cat_method = QWidget()
        lay = QVBoxLayout(self.page_cat_method)
        lay.addWidget(QLabel("<h3>3) Kategorien anlegen</h3>"))

        # Count existing categories
        try:
            cnt = int(self.conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"])
        except Exception:
            cnt = 0

        hint = QLabel(
            "Du kannst Kategorien direkt im <b>Kategorien-Manager</b> erstellen, oder über eine <b>Excel-Vorlage</b> importieren."
            "<br><small>Beispiel-Pfad: Gesundheit › Krankenkasse › Prämie</small>"
        )
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        lay.addWidget(hint)

        gb = QGroupBox("Methode")
        vb = QVBoxLayout(gb)
        self.rb_cat_manager = QRadioButton("Kategorien-Manager verwenden (im Programm)")
        self.rb_cat_excel = QRadioButton("Excel-Vorlage exportieren → ausfüllen → importieren")
        self.rb_cat_manager.setChecked(True)
        vb.addWidget(self.rb_cat_manager)
        vb.addWidget(self.rb_cat_excel)
        lay.addWidget(gb)

        # Optional: clean start
        self.cb_clean_start = QCheckBox(f"Clean Start: vorhandene Kategorien löschen ({cnt} vorhanden)")
        # Nur erlauben, wenn Budget/Tracking leer sind
        allow_clean = self._is_safe_to_reset()
        self.cb_clean_start.setEnabled(bool(allow_clean and cnt > 0))
        if not allow_clean and cnt > 0:
            self.cb_clean_start.setToolTip("Dein Budget/Tracking enthält bereits Daten – Reset ist deaktiviert.")
        lay.addWidget(self.cb_clean_start)

        lay.addStretch(1)

        self.steps.append(_Step("Kategorien Methode", self.page_cat_method))

        # 4.1) Cat manager page
        self.page_cat_manager = QWidget()
        lay = QVBoxLayout(self.page_cat_manager)
        lay.addWidget(QLabel("<h3>4) Kategorien-Manager</h3>"))
        desc = QLabel(
            "Klicke auf <b>Öffnen</b>, lege deine Kategorien an, dann schließe den Dialog mit <b>OK</b>."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        self.btn_open_cat_manager = QPushButton("📁 Kategorien-Manager öffnen…")
        self.btn_open_cat_manager.clicked.connect(self._open_category_manager)
        lay.addWidget(self.btn_open_cat_manager)

        self.lbl_cat_done_1 = QLabel("<small>Noch nicht abgeschlossen.</small>")
        self.lbl_cat_done_1.setTextFormat(Qt.RichText)
        self.lbl_cat_done_1.setWordWrap(True)
        lay.addWidget(self.lbl_cat_done_1)
        lay.addStretch(1)

        self.steps.append(_Step("Kategorien-Manager", self.page_cat_manager, is_blocking=True))

        # 4.2) Excel export/import page
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

        self.btn_export_template = QPushButton("📤 Excel-Vorlage exportieren…")
        self.btn_export_template.clicked.connect(self._export_template)
        lay.addWidget(self.btn_export_template)

        self.btn_import_template = QPushButton("📥 Kategorien aus Excel importieren…")
        self.btn_import_template.clicked.connect(self._import_from_excel)
        lay.addWidget(self.btn_import_template)

        self.lbl_cat_done_2 = QLabel("<small>Noch nicht abgeschlossen.</small>")
        self.lbl_cat_done_2.setTextFormat(Qt.RichText)
        self.lbl_cat_done_2.setWordWrap(True)
        lay.addWidget(self.lbl_cat_done_2)

        lay.addStretch(1)

        self.steps.append(_Step("Excel-Import", self.page_cat_excel, is_blocking=True))

        # 5) Budget tab as *window* (fill-in) – blocking until opened once
        self.page_budget_load = QWidget()
        lay = QVBoxLayout(self.page_budget_load)
        lay.addWidget(QLabel("<h3>5) Budget ausfüllen</h3>"))

        desc = QLabel(
            "Der Budget-Tab wird jetzt als <b>eigenes Fenster</b> geöffnet, damit du ihn direkt ausfüllen kannst.<br><br>"
            "• Kategorien werden aus der Datenbank geladen.<br>"
            "• Du trägst Monatswerte in die Tabelle ein.<br>"
            "• Danach schließt du das Budget-Fenster und klickst hier auf <b>Weiter</b>."
        )
        desc.setTextFormat(Qt.RichText)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        self.btn_open_budget_window = QPushButton("💰 Budget-Fenster öffnen…")
        self.btn_open_budget_window.clicked.connect(self._open_budget_window)
        lay.addWidget(self.btn_open_budget_window)

        self.lbl_budget_done = QLabel("<small>Noch nicht geöffnet.</small>")
        self.lbl_budget_done.setTextFormat(Qt.RichText)
        self.lbl_budget_done.setWordWrap(True)
        lay.addWidget(self.lbl_budget_done)

        lay.addStretch(1)

        self.steps.append(
            _Step(
                "Budget ausfüllen",
                self.page_budget_load,
                on_enter=self._enter_budget_tab_and_open_budget_window_once,
                is_blocking=True,
            )
        )

        # 6) Budget tab explain
        self.page_budget_explain = self._mk_page(
            "6) Budget-Tab – Bearbeiten, Setzen, Tabelle",
            "<b>6.1 Kategorien bearbeiten</b><br>"
            "• Rechtsklick auf eine Zeile (oder ⚙/Dialog) → Umbenennen, Löschen, Flags setzen.<br><br>"
            "<b>6.2 Budget setzen</b><br>"
            "• In den Monatsspalten direkt Beträge eintragen (CHF).<br>"
            "• Total wird automatisch berechnet.<br><br>"
            "<b>6.3 Tabelle erklärt</b><br>"
            "• Spalte <b>⭐ Fix</b>: Fixkosten markieren (z. B. Miete).<br>"
            "• Spalte <b>∞ Wiederkehrend</b>: wiederkehrende Buchung (z. B. Monatsabo).<br>"
            "• Spalte <b>Tag</b>: Fälligkeitstag im Monat (1–31)."
        )
        self.steps.append(_Step("Budget Erklärung", self.page_budget_explain, on_enter=self._enter_budget_tab))

        # 7) Tracking - first booking
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

        self.btn_add_first = QPushButton("➕ Erste Buchung hinzufügen…")
        self.btn_add_first.clicked.connect(self._open_first_booking)
        lay.addWidget(self.btn_add_first)

        lay.addStretch(1)

        self.steps.append(_Step("Tracking erste Buchung", self.page_tracking_first, on_enter=self._enter_tracking_tab))

        # 8) Tracking - fixcosts
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

        self.btn_open_fix = QPushButton("★ Fix/Wiederkehrend buchen…")
        self.btn_open_fix.clicked.connect(self._open_fix_dialog)
        lay.addWidget(self.btn_open_fix)

        lay.addStretch(1)

        self.steps.append(_Step("Tracking Fix", self.page_tracking_fix, on_enter=self._enter_tracking_tab))

        # Finish page
        self.page_finish = QWidget()
        lay = QVBoxLayout(self.page_finish)
        lay.addWidget(QLabel("<h3>Fertig ✅</h3>"))
        done = QLabel(
            "Du hast den Quick-Guide abgeschlossen.<br><br>"
            "Tipps:<br>"
            "• Kategorien-Pfad hilft überall (z. B. Gesundheit › Krankenkasse › Prämie).<br>"
            "• Budget = Plan, Tracking = Realität.<br>"
            "• Dashboard/Übersicht vergleicht Budget vs. Getracked."
        )
        done.setTextFormat(Qt.RichText)
        done.setWordWrap(True)
        lay.addWidget(done)

        # Nach Abschluss des Assistenten standardmäßig NICHT mehr beim Start anzeigen
        self.cb_show_on_start_end = QCheckBox("Einführung beim nächsten Start erneut anzeigen")
        self.cb_show_on_start_end.setChecked(False)  # Standard: Aus nach Abschluss
        lay.addWidget(self.cb_show_on_start_end)

        lay.addStretch(1)

        self.steps.append(_Step("Fertig", self.page_finish))

        self._step_done = [False] * len(self.steps)
        # blocking steps initial false, others true
        for i, st in enumerate(self.steps):
            self._step_done[i] = not st.is_blocking

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
            except Exception:
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
        """Beim Schließen: Einstellung 'Einführung beim Start anzeigen' persistieren.

        Wichtig:
        - Nicht automatisch als abgeschlossen markieren (setup_completed bleibt False),
          außer der User hat aktiv 'Fertig' geklickt.
        """
        try:
            if hasattr(self, "cb_show_on_start_end") and self.stack.currentWidget() is self.page_finish:
                self.settings.set("show_onboarding", bool(self.cb_show_on_start_end.isChecked()))
            elif hasattr(self, "cb_show_on_start"):
                self.settings.set("show_onboarding", bool(self.cb_show_on_start.isChecked()))
        except Exception:
            pass
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
        except Exception:
            pass

    def _enter_tracking_tab(self) -> None:
        try:
            if hasattr(self.main_window, "_goto_tab"):
                self.main_window._goto_tab(self.main_window.tracking_tab)
            else:
                self.main_window.tabs.setCurrentWidget(self.main_window.tracking_tab)
            if hasattr(self.main_window.tracking_tab, "refresh"):
                self.main_window.tracking_tab.refresh()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Actions (pages)
    # ---------------------------------------------------------------------
    def _open_category_manager(self) -> None:
        try:
            self.main_window._show_category_manager()
            # manager is modal; when it closes, consider done if there is at least one category
            cnt = int(self.conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"])
            if cnt <= 0:
                QMessageBox.information(self, "Hinweis", "Noch keine Kategorien vorhanden. Du kannst trotzdem fortfahren.")
            self._cats_done = True
            self._step_done[3] = True
            self.lbl_cat_done_1.setText("<small>✅ Kategorien-Manager abgeschlossen.</small>")
            self._update_nav()
            self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Kategorien-Manager konnte nicht geöffnet werden:\n{e}")

    def _export_template(self) -> None:
        try:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Ordner wählen – Excel-Vorlage speichern",
                str(Path.home()),
            )
            if not folder:
                return
            out = Path(folder) / "Budgetmanager_Kategorien_Template.xlsx"
            export_category_template_xlsx(out)
            QMessageBox.information(
                self,
                "OK",
                f"Vorlage gespeichert:\n{out}\n\nÖffne die Datei in Excel, fülle sie aus, und komme dann zurück zum Import.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Export fehlgeschlagen:\n{e}")

    def _import_from_excel(self) -> None:
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Kategorien-Excel auswählen",
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
            QMessageBox.information(self, "Kontrolle", "Zur Kontrolle öffnet sich jetzt der Kategorien-Manager.")
            self.main_window._show_category_manager()

            self._cats_done = True
            self._step_done[4] = True
            self.lbl_cat_done_2.setText("<small>✅ Excel-Import abgeschlossen.</small>")
            self._update_nav()
            self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Import fehlgeschlagen:\n{e}")

    def _open_first_booking(self) -> None:
        try:
            # tracking_tab.add() öffnet den Dialog und speichert bei OK
            if hasattr(self.main_window.tracking_tab, "add"):
                self.main_window.tracking_tab.add()
                self.main_window.tracking_tab.refresh()
            else:
                QMessageBox.information(self, "Hinweis", "Tracking-Dialog nicht verfügbar.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Dialog konnte nicht geöffnet werden:\n{e}")

    def _open_fix_dialog(self) -> None:
        try:
            if hasattr(self.main_window.tracking_tab, "add_fixcosts"):
                self.main_window.tracking_tab.add_fixcosts()
            else:
                QMessageBox.information(self, "Hinweis", "Fix/Wiederkehrend-Dialog nicht verfügbar.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Dialog konnte nicht geöffnet werden:\n{e}")

    def _enter_budget_tab_and_open_budget_window_once(self) -> None:
        """Wechselt in den Budget-Tab und öffnet beim ersten Eintritt das Budget-Fenster."""
        self._enter_budget_tab()
        if not self._budget_opened_once:
            self._open_budget_window(auto=True)

    def _open_budget_window(self, *, auto: bool = False) -> None:
        """Öffnet ein separates Budget-Fenster zum direkten Ausfüllen."""
        try:
            dlg = BudgetFillDialog(self.main_window, self.conn, title="💰 Budget ausfüllen (Setup)")
            dlg.exec()

            self._budget_opened_once = True
            self._budget_done = True

            # Step-Index: 5 (nach Start/DB/Kat-Methode/Kat-Seiten)
            if len(self._step_done) > 5:
                self._step_done[5] = True

            if hasattr(self, "lbl_budget_done"):
                self.lbl_budget_done.setText("<small>✅ Budget-Fenster wurde geöffnet.</small>")
            self._update_nav()

            # Tabs neu laden (Budget/Übersicht hängen davon ab)
            if hasattr(self.main_window, "_refresh_all_tabs"):
                self.main_window._refresh_all_tabs()
        except Exception as e:
            # Auto-Open soll UI nicht nerven – Button-Open darf Fehler zeigen
            if not auto:
                QMessageBox.critical(self, "Fehler", f"Budget-Fenster konnte nicht geöffnet werden:\n{e}")

    # ---------------------------------------------------------------------
    # Safety helpers
    # ---------------------------------------------------------------------
    def _is_safe_to_reset(self) -> bool:
        try:
            b = int(self.conn.execute("SELECT COUNT(*) AS c FROM budget").fetchone()["c"])
        except Exception:
            b = 0
        try:
            t = int(self.conn.execute("SELECT COUNT(*) AS c FROM tracking").fetchone()["c"])
        except Exception:
            t = 0
        # nur wenn Budget+Tracking leer sind
        return (b == 0 and t == 0)

    def _reset_categories(self) -> None:
        try:
            if not self._is_safe_to_reset():
                QMessageBox.warning(self, "Nicht möglich", "Reset ist deaktiviert, weil bereits Daten vorhanden sind.")
                return
            if QMessageBox.question(
                self,
                "Clean Start",
                "Wirklich alle Kategorien löschen? (Budget/Tracking sind leer – daher sicher)",
            ) != QMessageBox.Yes:
                self.cb_clean_start.setChecked(False)
                return

            self.conn.execute("DELETE FROM categories")
            self.conn.commit()
            QMessageBox.information(self, "OK", "Kategorien wurden gelöscht.")
            self.main_window._refresh_all_tabs()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Reset fehlgeschlagen:\n{e}")
