OpenAI Codex v0.106.0 (research preview)
--------
workdir: /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager
model: gpt-5.3-codex
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: low
reasoning summaries: none
session id: 019cb33b-cb53-7b23-bf56-fe213b747d6c
--------
user
Implement: Analysiere und fixe budget_tab.py: Parent-Zellen READ-ONLY, fmt_amount(0) Fix, total=puffer+kinder anzeigen, v1.0.16. Use multi-agent roles: explorer then worker then reviewer. Keep changes minimal. Run python -m compileall . and keep output concise.
mcp startup: no servers
codex
Ich setze das jetzt in der gewünschten Reihenfolge um: erst `explorer` zur gezielten Analyse von `budget_tab.py`, dann `worker` für minimale Änderungen, danach `reviewer` zur Risiko-Prüfung. Anschließend führe ich `python -m compileall .` (und den i18n-Check laut Repo-Regeln) aus.
collab spawn_agent(call_1Bld0BrVDwlJNoAZHXbeNcWz, prompt="Untersuche gezielt budget_tab.py für folgende Punkte und liefere einen minimalen Änderungsplan mit präzisen Stellen (Dat…")
mcp startup: no servers
spawn_agent(call_1Bld0BrVDwlJNoAZHXbeNcWz, prompt="Untersuche gezielt budget_tab.py für folgende Punkte und liefere einen minimalen Änderungsplan mit präzisen Stellen (Dat…") pending init:
  agent: 019cb33b-f0a4-7972-bea0-e0117aa9b1f5
collab wait(call_gdYdSmbKMy0epnBQc9YAqVP9)
  receivers: 019cb33b-f0a4-7972-bea0-e0117aa9b1f5
codex
Ich prüfe jetzt gezielt `budget_tab.py` und die Stelle für die Versionsnummer, ohne Repo-Vollscan. Danach liefere ich einen minimalen Änderungsplan mit konkreten Dateipfaden und groben Zeilenbereichen.
exec
/usr/bin/zsh -lc "sed -n '1,260p' budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "rg --files | rg 'budget_tab.py|version|__init__.py|pyproject.toml|setup.cfg|setup.py'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager exited 2 in 50ms:
sed: can't read budget_tab.py: No such file or directory
 succeeded in 51ms:
version.json
views/tabs/budget_tab.py
model/__init__.py
utils/__init__.py
updater/__init__.py
docs/archive/version-info.txt
codex
Ich habe den relevanten Pfad gefunden: `views/tabs/budget_tab.py`. Als Nächstes lese ich diese Datei und `version.json`, um die vier Punkte exakt zu verorten.
exec
/usr/bin/zsh -lc "sed -n '1,320p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3

from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog,
    QMenu, QInputDialog
)

from utils.i18n import tr, trf
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, is_income
from utils.i18n import display_typ, db_typ_from_display, tr_category_name
from model.category_model import CategoryModel, Category
from model.budget_model import BudgetModel
from model.favorites_model import FavoritesModel
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
exec
/usr/bin/zsh -lc 'cat version.json' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
{
  "app": "Budgetmanager",
  "version": "1.0.15"
}
codex
Ich habe die Versionsdatei bereits gefunden (`1.0.15`). Jetzt lese ich in `budget_tab.py` nur die relevanten Funktionsblöcke (Editierbarkeit, Betrag-Format, Total-Berechnung), um die Änderungen punktgenau zu planen.
exec
/usr/bin/zsh -lc "sed -n '320,760p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc 'rg -n "fmt_amount|ItemIsEditable|total|Total|buffer|puffer|_recalc|itemChanged|ROLE_HAS_CHILDREN|children|footer|sum|_parse_cell_amount" views/tabs/budget_tab.py' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
36:ROLE_HAS_CHILDREN = Qt.UserRole + 3 # bool
49:def fmt_amount(val: float) -> str:
55:def _parse_cell_amount(text: str) -> float:
59:        return sum(parse_amount(p) for p in raw.split(" + "))
68:    - Leaf-Kategorien: editierbar (Monate + Total)
70:      Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
89:        # Cache: (typ, cat) -> {month:int -> buffer(float)}
90:        self._buffer_cache: dict[tuple[str, str], dict[int, float]] = {}
137:        # Bezeichnung + Fix + Wiederh. + Tag + 12 Monate + Total
139:        self.table.setHorizontalHeaderLabels([tr("header.designation"), tr("header.fix"), tr("header.recurring_symbol"), tr("header.day")] + _months() + [tr("header.total")])
158:        self.table.itemChanged.connect(self._on_item_changed)
196:        summary = QHBoxLayout()
197:        summary.addWidget(self.lbl_overview)
198:        summary.addStretch(1)
199:        root.addLayout(summary)
237:                # Spalten: 0=Bezeichnung, 1=Fix, 2=∞, 3=Tag, 4-15=Monate, 16=Total
244:                    if next_c > 16:  # nach Total -> nächste Zeile
256:    def _is_footer_row(self, r: int) -> bool:
326:    def _row_has_children(self, r: int) -> bool:
330:        v = it0.data(ROLE_HAS_CHILDREN)
 succeeded in 51ms:
        it0 = self.table.item(r, 0)
        if not it0:
            return -1
        d = it0.data(ROLE_DEPTH)
        return int(d) if d is not None else -1

    def _row_has_children(self, r: int) -> bool:
        it0 = self.table.item(r, 0)
        if not it0:
            return False
        v = it0.data(ROLE_HAS_CHILDREN)
        return bool(v)

    # -----------------------------
    # Tree build + totals
    # -----------------------------
    def _build_tree_flat(self, typ: str, matrix: dict[str, dict[int, float]]):
        """Returns flattened rows with computed totals.

        Returns:
codex
Ich habe die Kernlogik identifiziert; mir fehlt noch der direkte Block zur Editierbarkeit der Monatszellen und zur Total-Textbildung, damit ich die Zeilenbereiche sauber benennen kann. Ich lese dafür nur den restlichen relevanten Ausschnitt.
exec
/usr/bin/zsh -lc "sed -n '760,1360p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
                            lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(own_val)}", _SEP]
                            for ch in ch_names:
                                ch_v = float(totals_by_name.get(ch, {}).get(m, 0.0))
                                lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_v)}")
                            ch_sum = sum(
                                float(totals_by_name.get(ch, {}).get(m, 0.0))
                                for ch in ch_names
                            )
                            lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_sum)}"]
                            it.setToolTip("\n".join(lines))
                        else:
                            it.setToolTip(path)

                        self.table.setItem(r, col_idx, it)
                        row_total      += total_val
                        row_buf_total  += own_val
                        row_child_total += child_val

                    if has_children:
                        ch_names = direct_children_by_name.get(name, [])
codex
Ich habe die betroffenen Blöcke identifiziert und hole jetzt noch Zeilennummern (grob) für einen präzisen, minimalen Plan.
exec
/usr/bin/zsh -lc "nl -ba views/tabs/budget_tab.py | sed -n '40,90p;730,840p;1060,1235p;1270,1315p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
    40	
    41	
    42	from utils.money import parse_money
    43	from views.ui_colors import ui_colors
    44	
    45	def parse_amount(text: str) -> float:
    46	    return parse_money(text)
    47	
    48	
    49	def fmt_amount(val: float) -> str:
    50	    if abs(val) < 1e-9:
    51	        return ""
    52	    return f"{val:.2f}"
    53	
    54	
    55	def _parse_cell_amount(text: str) -> float:
    56	    """Parst eine Betrags-Zelle, auch im Format 'Kinder + Puffer' oder '1600.00+'."""
    57	    raw = (text or "").strip().rstrip("+").strip()
    58	    if " + " in raw:
    59	        return sum(parse_amount(p) for p in raw.split(" + "))
codex
Ich prüfe noch kurz, ob `1.0.15` außer `version.json` irgendwo hart kodiert ist, damit die Versionsanhebung vollständig bleibt.
exec
/usr/bin/zsh -lc "rg -n \"1\\.0\\.15|version\\.json|\\\"version\\\"\" -g '"'!docs/**'"'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
version.json:3:  "version": "1.0.15"
app_info.py:17:APP_VERSION = "1.0.15"
CHANGELOG.md:8:## [1.0.15] - 2026-03-03
CHANGELOG.md:22:- Version: app_info.py + version.json auf 1.0.15 aktualisiert.
latest.json.template:4:  "version": "1.0.0",
data/default_categories.json:3:    "version": "1.0",
updater/common.py:82:        p = app_dir() / "version.json"
updater/common.py:85:            return str(data.get("version", "0.0.0"))
updater/common.py:103:        version=str(data.get("version", "0.0.0")).strip(),
updater/common.py:172:        "version": version_str,
updater/generate_manifest.py:68:        "version": args.version,
updater/github_manifest.py:32:    version = str(data.get("version", "")).strip()
codex
Relevante Dateien (gezielt geprüft):
- [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py)
- [version.json](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/version.json)
- [app_info.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/app_info.py)

Minimaler Änderungsplan:

1. Parent-Zellen read-only machen  
- Datei: [budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py)  
- Stelle A: ca. Zeile `749-756` (Monatszellen-Aufbau in `load`)  
  - Bei `has_children` für Monatszellen `it.setFlags(it.flags() & ~Qt.ItemIsEditable)` setzen.  
- Stelle B: ca. Zeile `1090-1095` (`_on_item_changed`)  
  - Branch für Parent-Monatsedit deaktivieren/entfernen: bei `has_children and 4 <= c <= 15` sofort `return`.  
- Stelle C (aufräumen): ca. Zeile `1174+`  
  - `_handle_parent_month_edit` wird danach ungenutzt; optional entfernen (nicht zwingend für Minimalfix).

2. `fmt_amount(0)` Darstellung fixen  
- Datei: [budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py)  
- Stelle: ca. Zeile `49-52` (`fmt_amount`)  
  - Statt `""` bei `abs(val) < 1e-9` auf `"0.00"` gehen (ggf. auch `-0.00` abfangen).

3. Total als `puffer + kinder` anzeigen (Parent)  
- Datei: [budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py)  
- Stelle A: ca. Zeile `778-793` (Initial-Totaltext in `load`)  
  - Für `has_children` statt Marker-Text (`1234.00+`) auf explizites Format umstellen, z. B. `"{children} + {puffer}"` mit `row_child_total` und `row_buf_total`.  
- Stelle B: ca. Zeile `1275-1297` (`_recalc_row_total`)  
  - Parent-Fall gesondert formatieren, damit nach Recalc nicht wieder nur ein Einzelwert gesetzt wird.  
- Optional Konsistenz: ca. Zeile `778-789` Tooltip nutzt aktuell bei `puffer` fälschlich `row_total` statt `row_buf_total`.

4. Version auf `v1.0.16`  
- Datei: [version.json](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/version.json): Zeile `3` von `1.0.15` auf `1.0.16`.  
- Datei: [app_info.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/app_info.py): ca. Zeile `17` `APP_VERSION` ebenfalls auf `1.0.16`.
wait(call_gdYdSmbKMy0epnBQc9YAqVP9) 1 agents complete:
  019cb33b-f0a4-7972-bea0-e0117aa9b1f5 completed: "Relevante Dateien (gezielt geprüft):
- [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/G…"
codex
Die Analyse ist da und passt zu deinem Scope. Ich lasse jetzt einen `worker` die minimalen Änderungen exakt an diesen Stellen umsetzen und danach prüfe ich per `reviewer`.
collab spawn_agent(call_nZezMFhlNmSXpUWycUcvNdrp, prompt="Setze minimal folgende Änderungen um:
1) In views/tabs/budget_tab.py: Parent-Monatszellen read-only machen (UI + Guard i…")
spawn_agent(call_nZezMFhlNmSXpUWycUcvNdrp, prompt="Setze minimal folgende Änderungen um:
1) In views/tabs/budget_tab.py: Parent-Monatszellen read-only machen (UI + Guard i…") pending init:
  agent: 019cb33c-e147-7931-a255-47594da1364b
mcp startup: no servers
collab wait(call_iIVNV7SF7ZnpThS5kGM9bZBB)
  receivers: 019cb33c-e147-7931-a255-47594da1364b
codex
Ich setze die vier Punkte minimal-invasiv um und prüfe dafür zuerst gezielt die betroffenen Dateien/Funktionen (`budget_tab.py`, `version.json`, `app_info.py`) inklusive der bestehenden Parent/Child-Logik.
exec
/usr/bin/zsh -lc 'rg -n "def fmt_amount|_on_item_changed|parent|total|buffer|version" views/tabs/budget_tab.py version.json app_info.py' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "sed -n '260,620p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "sed -n '1,260p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "cat version.json && echo '---' && sed -n '1,220p' app_info.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 50ms:
app_info.py:33:def app_version_label() -> str:
version.json:3:  "version": "1.0.15"
views/tabs/budget_tab.py:49:def fmt_amount(val: float) -> str:
views/tabs/budget_tab.py:89:        # Cache: (typ, cat) -> {month:int -> buffer(float)}
views/tabs/budget_tab.py:90:        self._buffer_cache: dict[tuple[str, str], dict[int, float]] = {}
views/tabs/budget_tab.py:139:        self.table.setHorizontalHeaderLabels([tr("header.designation"), tr("header.fix"), tr("header.recurring_symbol"), tr("header.day")] + _months() + [tr("header.total")])
views/tabs/budget_tab.py:158:        self.table.itemChanged.connect(self._on_item_changed)
views/tabs/budget_tab.py:334:    # Tree build + totals
views/tabs/budget_tab.py:337:        """Returns flattened rows with computed totals.
views/tabs/budget_tab.py:342:          totals_by_name: dict[name][month] -> total (buffer + subtree)
views/tabs/budget_tab.py:343:          buffer_by_name: dict[name][month] -> own buffer (DB value)
views/tabs/budget_tab.py:351:        totals_by_name: dict[str, dict[int, float]] = {}
views/tabs/budget_tab.py:352:        buffer_by_name: dict[str, dict[int, float]] = {}
views/tabs/budget_tab.py:359:            total = dict(own)
views/tabs/budget_tab.py:363:                    total[m] = float(total.get(m, 0.0)) + float(ct.get(m, 0.0))
views/tabs/budget_tab.py:364:            totals_by_name[c.name] = total
views/tabs/budget_tab.py:365:            buffer_by_name[c.name] = own
views/tabs/budget_tab.py:368:            return total
views/tabs/budget_tab.py:393:        return flat, totals_by_name, buffer_by_name, direct_children_by_name
views/tabs/budget_tab.py:400:    def _is_total_row(self, r: int) -> bool:
 succeeded in 51ms:
    def _is_header_row(self, r: int) -> bool:
        it = self.table.item(r, 0)
        if not it:
            return False
        return (it.data(ROLE_CAT_REAL) is None) and it.text().startswith("═══")

    def _row_count_data(self) -> int:
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text() == "TOTAL":
                return r
        return self.table.rowCount()

    def _row_typ(self, r: int) -> str:
        it0 = self.table.item(r, 0)
        if it0:
            t = it0.data(ROLE_TYP)
            if t:
                return str(t)
        # fallback
 succeeded in 51ms:
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3

from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog,
    QMenu, QInputDialog
)

from utils.i18n import tr, trf
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, is_income
from utils.i18n import display_typ, db_typ_from_display, tr_category_name
from model.category_model import CategoryModel, Category
from model.budget_model import BudgetModel
from model.favorites_model import FavoritesModel
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
 succeeded in 51ms:
{
  "app": "Budgetmanager",
  "version": "1.0.15"
}---
from __future__ import annotations

"""Zentrale App-Metadaten (Name/Version/Release-Datum).

Best Practice:
- Version nur hier ändern.
- GUI (Fenstertitel, Über-Dialog), Updater, Logs usw. lesen diese Werte.

Hinweis:
Die Codebasis hieß historisch "v2.2.0 ... fix2" – für Releases verwenden wir aber 0.x.x.x,
solange das Projekt noch nicht "fertig" ist.
"""

APP_NAME = "Budgetmanager"

# SemVer-ähnlich, aber mit 4 Stellen wie von dir gewünscht: 0.MAJOR.MINOR.PATCH
codex
Ich habe die Treffer; als Nächstes lese ich die relevanten Blöcke rund um `load`, Parent-Zellenflags, `_on_item_changed` und Parent-Recalc, damit die Änderungen konsistent bleiben und nur punktuell eingreifen.
exec
/usr/bin/zsh -lc "sed -n '860,1115p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "sed -n '1115,1325p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "sed -n '620,860p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
                cat_obj = c_obj
                break

        if not cat_obj or not cat_obj.is_recurring:
            return

        try:
            new_day = int(item.text())
            if new_day < 1 or new_day > 31:
                raise ValueError("Tag muss 1-31 sein")
        except Exception:
            self._internal_change = True
            item.setText(str(cat_obj.recurring_day or 1))
            self._internal_change = False
            QMessageBox.warning(self, tr("msg.info"), tr("msg.invalid_day"))
            return

        self.cats.update_flags(cat_obj.id, is_fix=bool(cat_obj.is_fix), is_recurring=True, recurring_day=new_day)

    def _handle_total_column_edit(self, item: QTableWidgetItem, r: int, typ: str, cat: str) -> None:
 succeeded in 51ms:
        sep = "─" * 28
        lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(puffer_val)}", sep]
        for ch_name, ch_val in children:
            lines.append(f"  {ch_name}:  {fmt_amount(ch_val)}")
        lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(children_sum)}"]
        return "\n".join(lines)

    def _sum_immediate_children_month(self, parent_row: int, month_col: int) -> float:
        """Summe der unmittelbaren Children (depth+1) für einen Monat.

        Wichtig: Wir summieren NUR depth+1-Zeilen, weil diese bereits ihre Subtrees enthalten.
        """
        parent_depth = self._row_depth(parent_row)
        if parent_depth < 0:
            return 0.0

        data_rows = self._row_count_data()
        total = 0.0
        i = parent_row + 1
        while i < data_rows:
 succeeded in 50ms:
                    self.table.insertRow(r)
                    header_item = QTableWidgetItem(f"═══ {display_typ(t)} ═══")
                    header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
                    font = header_item.font()
                    font.setBold(True)
                    header_item.setFont(font)
                    try:
                        col = self._typ_color(t)
                        header_item.setForeground(QBrush(col))

                        # Sichtbarer Farb-Header: komplette Zeile dezent einfärben
                        from PySide6.QtGui import QColor
                        bg = QColor(col)
                        bg.setAlpha(35)
                        header_item.setBackground(QBrush(bg))
                        # Restliche Zellen werden erst nach dem Insert gesetzt → später unten nachziehen
                    except Exception as e:
                        logger.debug("header_item color failed: %s", e)
                    header_item.setData(ROLE_TYP, t)
                    self.table.setItem(r, 0, header_item)
codex
Ich habe die Ursachen lokalisiert: `fmt_amount` leert 0-Werte, Parent-Monatszellen sind aktuell noch editierbar, und bei Parent-Total gibt es Inkonsistenzen zwischen `load()` und `_recalc_row_total()`. Ich mache jetzt einen kleinen Patch nur in den betroffenen Funktionen plus Versionsdateien.
file update
M /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager/views/tabs/budget_tab.py
@@ -50,3 +50,3 @@
     if abs(val) < 1e-9:
-        return ""
+        return "0.00"
     return f"{val:.2f}"
@@ -756,2 +756,4 @@
                         it.setData(ROLE_TYP, t)
+                        if has_children:
+                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
 
@@ -779,3 +781,3 @@
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_total)}", _SEP]
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
                         for ch in ch_names:
@@ -1083,2 +1085,5 @@
             return
+        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
+        if has_children and 4 <= c <= 15:
+            return
 
@@ -1282,2 +1287,3 @@
             return  # Total-Zeile wird separat berechnet
+        has_children = self._row_has_children(r)
 
@@ -1295,3 +1301,38 @@
         try:
-            tot.setText(fmt_amount(row_total))
+            if has_children:
+                _pm = tr("budget.parent.marker")
+                typ = self._row_typ(r)
+                cat = self._row_cat_real(r)
+                row_buf_total = 0.0
+                row_child_total = 0.0
+                if cat:
+                    for m in range(1, 13):
+                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
+                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
+                sep = "─" * 26
+                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
+                data_rows = self._row_count_data()
+                parent_depth = self._row_depth(r)
+                i = r + 1
+                while i < data_rows:
+                    if self._is_header_row(i):
+                        break
+                    d = self._row_depth(i)
+                    if d <= parent_depth:
+                        break
+                    if d == parent_depth + 1:
+                        ch_cat = self._row_cat_real(i)
+                        if ch_cat:
+                            ch_year = 0.0
+                            for mm in range(4, 16):
+                                it_ch = self.table.item(i, mm)
+                                ch_year += parse_amount(it_ch.text() if it_ch else "")
+                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
+                    i += 1
+                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
+                tot.setText(f"{fmt_amount(row_total)}{_pm}")
+                tot.setToolTip("\n".join(tot_lines))
+                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
+            else:
+                tot.setText(fmt_amount(row_total))
             tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
apply_patch(auto_approved=true) exited 0 in 10ms:
Success. Updated the following files:
M views/tabs/budget_tab.py
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index b8bfe4062f757333b86e5426de8c0dc0468438b3..4500fc4b518ddb04f28ecf736ca987fce0b735cb
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -48,7 +48,7 @@
 
 def fmt_amount(val: float) -> str:
     if abs(val) < 1e-9:
-        return ""
+        return "0.00"
     return f"{val:.2f}"
 
 
@@ -754,6 +754,8 @@
                         it = QTableWidgetItem(_cell_text)
                         it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                         it.setData(ROLE_TYP, t)
+                        if has_children:
+                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
 
                         if has_children:
                             ch_names = direct_children_by_name.get(name, [])
@@ -777,7 +779,7 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_total)}", _SEP]
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -1081,6 +1083,9 @@
         # Parent + Children: Total-Spalte ist read-only
         if has_children and c == 16:
             return
+        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
+        if has_children and 4 <= c <= 15:
+            return
 
         # Total-Spalte → auf Monate verteilen (nur Leaf)
         if c == 16 and not has_children:
@@ -1280,6 +1285,7 @@
             return
         if self._is_total_row(r):
             return  # Total-Zeile wird separat berechnet
+        has_children = self._row_has_children(r)
 
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
@@ -1293,7 +1299,42 @@
 
         self._internal_change = True
         try:
-            tot.setText(fmt_amount(row_total))
+            if has_children:
+                _pm = tr("budget.parent.marker")
+                typ = self._row_typ(r)
+                cat = self._row_cat_real(r)
+                row_buf_total = 0.0
+                row_child_total = 0.0
+                if cat:
+                    for m in range(1, 13):
+                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
+                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
+                sep = "─" * 26
+                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
+                data_rows = self._row_count_data()
+                parent_depth = self._row_depth(r)
+                i = r + 1
+                while i < data_rows:
+                    if self._is_header_row(i):
+                        break
+                    d = self._row_depth(i)
+                    if d <= parent_depth:
+                        break
+                    if d == parent_depth + 1:
+                        ch_cat = self._row_cat_real(i)
+                        if ch_cat:
+                            ch_year = 0.0
+                            for mm in range(4, 16):
+                                it_ch = self.table.item(i, mm)
+                                ch_year += parse_amount(it_ch.text() if it_ch else "")
+                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
+                    i += 1
+                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
+                tot.setText(f"{fmt_amount(row_total)}{_pm}")
+                tot.setToolTip("\n".join(tot_lines))
+                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
+            else:
+                tot.setText(fmt_amount(row_total))
             tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
         finally:
             self._internal_change = False

file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index b8bfe4062f757333b86e5426de8c0dc0468438b3..4500fc4b518ddb04f28ecf736ca987fce0b735cb
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -48,7 +48,7 @@
 
 def fmt_amount(val: float) -> str:
     if abs(val) < 1e-9:
-        return ""
+        return "0.00"
     return f"{val:.2f}"
 
 
@@ -754,6 +754,8 @@
                         it = QTableWidgetItem(_cell_text)
                         it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                         it.setData(ROLE_TYP, t)
+                        if has_children:
+                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
 
                         if has_children:
                             ch_names = direct_children_by_name.get(name, [])
@@ -777,7 +779,7 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_total)}", _SEP]
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -1081,6 +1083,9 @@
         # Parent + Children: Total-Spalte ist read-only
         if has_children and c == 16:
             return
+        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
+        if has_children and 4 <= c <= 15:
+            return
 
         # Total-Spalte → auf Monate verteilen (nur Leaf)
         if c == 16 and not has_children:
@@ -1280,6 +1285,7 @@
             return
         if self._is_total_row(r):
             return  # Total-Zeile wird separat berechnet
+        has_children = self._row_has_children(r)
 
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
@@ -1293,7 +1299,42 @@
 
         self._internal_change = True
         try:
-            tot.setText(fmt_amount(row_total))
+            if has_children:
+                _pm = tr("budget.parent.marker")
+                typ = self._row_typ(r)
+                cat = self._row_cat_real(r)
+                row_buf_total = 0.0
+                row_child_total = 0.0
+                if cat:
+                    for m in range(1, 13):
+                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
+                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
+                sep = "─" * 26
+                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
+                data_rows = self._row_count_data()
+                parent_depth = self._row_depth(r)
+                i = r + 1
+                while i < data_rows:
+                    if self._is_header_row(i):
+                        break
+                    d = self._row_depth(i)
+                    if d <= parent_depth:
+                        break
+                    if d == parent_depth + 1:
+                        ch_cat = self._row_cat_real(i)
+                        if ch_cat:
+                            ch_year = 0.0
+                            for mm in range(4, 16):
+                                it_ch = self.table.item(i, mm)
+                                ch_year += parse_amount(it_ch.text() if it_ch else "")
+                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
+                    i += 1
+                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
+                tot.setText(f"{fmt_amount(row_total)}{_pm}")
+                tot.setToolTip("\n".join(tot_lines))
+                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
+            else:
+                tot.setText(fmt_amount(row_total))
             tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
         finally:
             self._internal_change = False

codex
Ich passe jetzt noch die Version konsistent auf `1.0.16` in `version.json` und `app_info.py` an.
exec
/usr/bin/zsh -lc "perl -0pi -e 's/\"version\": \"1\\.0\\.15\"/\"version\": \"1.0.16\"/g' version.json" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "perl -0pi -e 's/APP_VERSION = \"1\\.0\\.15\"/APP_VERSION = \"1.0.16\"/g' app_info.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:

 succeeded in 51ms:

file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index b8bfe4062f757333b86e5426de8c0dc0468438b3..4500fc4b518ddb04f28ecf736ca987fce0b735cb
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -48,7 +48,7 @@
 
 def fmt_amount(val: float) -> str:
     if abs(val) < 1e-9:
-        return ""
+        return "0.00"
     return f"{val:.2f}"
 
 
@@ -754,6 +754,8 @@
                         it = QTableWidgetItem(_cell_text)
                         it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                         it.setData(ROLE_TYP, t)
+                        if has_children:
+                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
 
                         if has_children:
                             ch_names = direct_children_by_name.get(name, [])
@@ -777,7 +779,7 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_total)}", _SEP]
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -1081,6 +1083,9 @@
         # Parent + Children: Total-Spalte ist read-only
         if has_children and c == 16:
             return
+        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
+        if has_children and 4 <= c <= 15:
+            return
 
         # Total-Spalte → auf Monate verteilen (nur Leaf)
         if c == 16 and not has_children:
@@ -1280,6 +1285,7 @@
             return
         if self._is_total_row(r):
             return  # Total-Zeile wird separat berechnet
+        has_children = self._row_has_children(r)
 
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
@@ -1293,7 +1299,42 @@
 
         self._internal_change = True
         try:
-            tot.setText(fmt_amount(row_total))
+            if has_children:
+                _pm = tr("budget.parent.marker")
+                typ = self._row_typ(r)
+                cat = self._row_cat_real(r)
+                row_buf_total = 0.0
+                row_child_total = 0.0
+                if cat:
+                    for m in range(1, 13):
+                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
+                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
+                sep = "─" * 26
+                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
+                data_rows = self._row_count_data()
+                parent_depth = self._row_depth(r)
+                i = r + 1
+                while i < data_rows:
+                    if self._is_header_row(i):
+                        break
+                    d = self._row_depth(i)
+                    if d <= parent_depth:
+                        break
+                    if d == parent_depth + 1:
+                        ch_cat = self._row_cat_real(i)
+                        if ch_cat:
+                            ch_year = 0.0
+                            for mm in range(4, 16):
+                                it_ch = self.table.item(i, mm)
+                                ch_year += parse_amount(it_ch.text() if it_ch else "")
+                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
+                    i += 1
+                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
+                tot.setText(f"{fmt_amount(row_total)}{_pm}")
+                tot.setToolTip("\n".join(tot_lines))
+                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
+            else:
+                tot.setText(fmt_amount(row_total))
             tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
         finally:
             self._internal_change = False

codex
Ich prüfe noch kurz die exakten Zeilenpositionen der Änderungen, damit ich dir präzise Funktions-/Zeilenangaben liefern kann (ohne Tests auszuführen).
exec
/usr/bin/zsh -lc "rg -n \"def fmt_amount|setFlags\\(it\\.flags\\(\\) & ~Qt\\.ItemIsEditable\\)|tot_lines = \\[f\\\"\\{tr\\('budget\\.tooltip\\.puffer'\\)\\}:  \\{fmt_amount\\(row_buf_total\\)\\}\\\"|if has_children and 4 <= c <= 15|def _recalc_row_total|APP_VERSION|\\\"version\\\"\" views/tabs/budget_tab.py app_info.py version.json" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 50ms:
version.json:3:  "version": "1.0.16"
views/tabs/budget_tab.py:49:def fmt_amount(val: float) -> str:
views/tabs/budget_tab.py:758:                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
views/tabs/budget_tab.py:782:                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
views/tabs/budget_tab.py:1087:        if has_children and 4 <= c <= 15:
views/tabs/budget_tab.py:1280:    def _recalc_row_total(self, r: int):
views/tabs/budget_tab.py:1313:                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
app_info.py:17:APP_VERSION = "1.0.16"
app_info.py:25:    return f"{APP_NAME} v{APP_VERSION}"
app_info.py:30:    return f"Über {APP_NAME} v{APP_VERSION}"
app_info.py:35:    return f"{APP_VERSION} ({APP_RELEASE_DATE})"
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index b8bfe4062f757333b86e5426de8c0dc0468438b3..4500fc4b518ddb04f28ecf736ca987fce0b735cb
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -48,7 +48,7 @@
 
 def fmt_amount(val: float) -> str:
     if abs(val) < 1e-9:
-        return ""
+        return "0.00"
     return f"{val:.2f}"
 
 
@@ -754,6 +754,8 @@
                         it = QTableWidgetItem(_cell_text)
                         it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                         it.setData(ROLE_TYP, t)
+                        if has_children:
+                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
 
                         if has_children:
                             ch_names = direct_children_by_name.get(name, [])
@@ -777,7 +779,7 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_total)}", _SEP]
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -1081,6 +1083,9 @@
         # Parent + Children: Total-Spalte ist read-only
         if has_children and c == 16:
             return
+        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
+        if has_children and 4 <= c <= 15:
+            return
 
         # Total-Spalte → auf Monate verteilen (nur Leaf)
         if c == 16 and not has_children:
@@ -1280,6 +1285,7 @@
             return
         if self._is_total_row(r):
             return  # Total-Zeile wird separat berechnet
+        has_children = self._row_has_children(r)
 
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
@@ -1293,7 +1299,42 @@
 
         self._internal_change = True
         try:
-            tot.setText(fmt_amount(row_total))
+            if has_children:
+                _pm = tr("budget.parent.marker")
+                typ = self._row_typ(r)
+                cat = self._row_cat_real(r)
+                row_buf_total = 0.0
+                row_child_total = 0.0
+                if cat:
+                    for m in range(1, 13):
+                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
+                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
+                sep = "─" * 26
+                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
+                data_rows = self._row_count_data()
+                parent_depth = self._row_depth(r)
+                i = r + 1
+                while i < data_rows:
+                    if self._is_header_row(i):
+                        break
+                    d = self._row_depth(i)
+                    if d <= parent_depth:
+                        break
+                    if d == parent_depth + 1:
+                        ch_cat = self._row_cat_real(i)
+                        if ch_cat:
+                            ch_year = 0.0
+                            for mm in range(4, 16):
+                                it_ch = self.table.item(i, mm)
+                                ch_year += parse_amount(it_ch.text() if it_ch else "")
+                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
+                    i += 1
+                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
+                tot.setText(f"{fmt_amount(row_total)}{_pm}")
+                tot.setToolTip("\n".join(tot_lines))
+                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
+            else:
+                tot.setText(fmt_amount(row_total))
             tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
         finally:
             self._internal_change = False

codex
Umgesetzt, minimal-invasiv und ohne Tests auszuführen.

Geänderte Stellen:

- `fmt_amount(0)` zeigt jetzt `0.00` statt leer:
  - [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py):49 (`fmt_amount`)

- Parent-Monatszellen read-only gemacht (UI) und Guard in `_on_item_changed`:
  - UI-Flags für Parent-Monatszellen in `load()`:
    - [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py):758
  - Guard gegen Parent-Monatsedits in `_on_item_changed`:
    - [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py):1087

- Parent-Total konsistent als `Puffer + Kinder` (Load + Recalc), Child/Leaf-Verhalten unverändert:
  - `load()`: Parent-Total-Tooltip korrigiert (Puffer-Zeile nutzt jetzt echten Puffer, nicht Gesamtsumme):
    - [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py):782
  - `_recalc_row_total()`: Parent-Total bleibt mit Parent-Marker, Tooltip zeigt `Puffer` und `Kinder-Summe`, Total bleibt read-only:
    - [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py):1280
    - [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py):1313

- Version auf `1.0.16`:
  - [version.json](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/version.json):3
  - [app_info.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/app_info.py):17
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index b8bfe4062f757333b86e5426de8c0dc0468438b3..4500fc4b518ddb04f28ecf736ca987fce0b735cb
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -48,7 +48,7 @@
 
 def fmt_amount(val: float) -> str:
     if abs(val) < 1e-9:
-        return ""
+        return "0.00"
     return f"{val:.2f}"
 
 
@@ -754,6 +754,8 @@
                         it = QTableWidgetItem(_cell_text)
                         it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                         it.setData(ROLE_TYP, t)
+                        if has_children:
+                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
 
                         if has_children:
                             ch_names = direct_children_by_name.get(name, [])
@@ -777,7 +779,7 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_total)}", _SEP]
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -1081,6 +1083,9 @@
         # Parent + Children: Total-Spalte ist read-only
         if has_children and c == 16:
             return
+        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
+        if has_children and 4 <= c <= 15:
+            return
 
         # Total-Spalte → auf Monate verteilen (nur Leaf)
         if c == 16 and not has_children:
@@ -1280,6 +1285,7 @@
             return
         if self._is_total_row(r):
             return  # Total-Zeile wird separat berechnet
+        has_children = self._row_has_children(r)
 
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
@@ -1293,7 +1299,42 @@
 
         self._internal_change = True
         try:
-            tot.setText(fmt_amount(row_total))
+            if has_children:
+                _pm = tr("budget.parent.marker")
+                typ = self._row_typ(r)
+                cat = self._row_cat_real(r)
+                row_buf_total = 0.0
+                row_child_total = 0.0
+                if cat:
+                    for m in range(1, 13):
+                        row_buf_total += float(self._buffer_cache.get((typ, cat), {}).get(m, 0.0))
+                        row_child_total += float(self._sum_immediate_children_month(r, m + 3))
+                sep = "─" * 26
+                tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", sep]
+                data_rows = self._row_count_data()
+                parent_depth = self._row_depth(r)
+                i = r + 1
+                while i < data_rows:
+                    if self._is_header_row(i):
+                        break
+                    d = self._row_depth(i)
+                    if d <= parent_depth:
+                        break
+                    if d == parent_depth + 1:
+                        ch_cat = self._row_cat_real(i)
+                        if ch_cat:
+                            ch_year = 0.0
+                            for mm in range(4, 16):
+                                it_ch = self.table.item(i, mm)
+                                ch_year += parse_amount(it_ch.text() if it_ch else "")
+                            tot_lines.append(f"  {tr_category_name(ch_cat)}:  {fmt_amount(ch_year)}")
+                    i += 1
+                tot_lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(row_child_total)}"]
+                tot.setText(f"{fmt_amount(row_total)}{_pm}")
+                tot.setToolTip("\n".join(tot_lines))
+                tot.setFlags(tot.flags() & ~Qt.ItemIsEditable)
+            else:
+                tot.setText(fmt_amount(row_total))
             tot.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
         finally:
             self._internal_change = False

wait(call_iIVNV7SF7ZnpThS5kGM9bZBB) 1 agents complete:
  019cb33c-e147-7931-a255-47594da1364b completed: "Umgesetzt, minimal-invasiv und ohne Tests auszuführen.

Geänderte Stellen:

- `fmt_amount(0)` zeigt jetzt `0.00` statt l…"
codex
Der `worker` hat die Zieländerungen gesetzt. Ich prüfe jetzt kurz den Diff lokal und gebe ihn an einen `reviewer` für eine gezielte Risiko-Kontrolle, bevor ich `compileall` ausführe.
exec
/usr/bin/zsh -lc 'git diff -- views/tabs/budget_tab.py version.json app_info.py' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc 'git status --short' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:

 succeeded in 51ms:
?? .ai/
?? .claude/
?? .codex/
?? .gemini/
?? .gitignore
?? AGENTS.md
?? ANALYSE_BUGFIX.md
?? ANALYSYS_PROGRAMM.md
?? BudgetManager.spec
?? CHANGELOG.md
?? CLAUDE.md
?? FEATURES.md
?? LICENSE.txt
?? MIGRATION.md
?? "Open Tasks.md"
?? README.md
?? README_INSTALLATION.md
?? RELEASE_CLEAN_NOTE.txt
?? SUMMARY.md
?? UI_KONSISTENZ_ANALYSE.md
collab spawn_agent(call_LCWvpd4clEh2V9Bf1gvVt0Ch, prompt="Review der implementierten Änderungen in:
- views/tabs/budget_tab.py
- version.json
- app_info.py
Ziel: finde Bugs/Risik…")
spawn_agent(call_LCWvpd4clEh2V9Bf1gvVt0Ch, prompt="Review der implementierten Änderungen in:
- views/tabs/budget_tab.py
- version.json
- app_info.py
Ziel: finde Bugs/Risik…") pending init:
  agent: 019cb33d-e063-7a81-bfff-792c86c605b3
mcp startup: no servers
codex
Ich prüfe jetzt gezielt die drei genannten Dateien auf die Anforderungen (Parent-Zellen read-only, `fmt_amount(0)`, Total-Anzeige = Puffer+Kinder, Version `1.0.16`) und liefere danach priorisierte Findings mit Zeilenhinweisen.
exec
/usr/bin/zsh -lc "nl -ba views/tabs/budget_tab.py | sed -n '1,260p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc 'nl -ba app_info.py' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc 'nl -ba version.json' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
     1	from __future__ import annotations
     2	import logging
     3	logger = logging.getLogger(__name__)
     4	import sqlite3
     5	
     6	from PySide6.QtCore import Qt, QEvent, Signal
     7	from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor, QPalette
     8	from PySide6.QtWidgets import (
     9	    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    10	    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog,
    11	    QMenu, QInputDialog
    12	)
    13	
    14	from utils.i18n import tr, trf
    15	from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, is_income
    16	from utils.i18n import display_typ, db_typ_from_display, tr_category_name
    17	from model.category_model import CategoryModel, Category
    18	from model.budget_model import BudgetModel
    19	from model.favorites_model import FavoritesModel
    20	from model.budget_warnings_model_extended import BudgetWarningsModelExtended
 succeeded in 51ms:
     1	from __future__ import annotations
     2	
     3	"""Zentrale App-Metadaten (Name/Version/Release-Datum).
     4	
     5	Best Practice:
     6	- Version nur hier ändern.
     7	- GUI (Fenstertitel, Über-Dialog), Updater, Logs usw. lesen diese Werte.
     8	
     9	Hinweis:
    10	Die Codebasis hieß historisch "v2.2.0 ... fix2" – für Releases verwenden wir aber 0.x.x.x,
    11	solange das Projekt noch nicht "fertig" ist.
    12	"""
    13	
    14	APP_NAME = "Budgetmanager"
    15	
    16	# SemVer-ähnlich, aber mit 4 Stellen wie von dir gewünscht: 0.MAJOR.MINOR.PATCH
    17	APP_VERSION = "1.0.16"
    18	
    19	# Nur Anzeige (About-Dialog). Kannst du jederzeit anpassen.
    20	APP_RELEASE_DATE = "3. März 2026"
 succeeded in 50ms:
     1	{
     2	  "app": "Budgetmanager",
     3	  "version": "1.0.16"
     4	}
codex
Parallel dazu lasse ich die geforderten Checks laufen, damit wir direkt ein verifiziertes Ergebnis haben.
codex
Ich habe die Versionsdateien geprüft; beide stehen auf `1.0.16`. Als Nächstes gehe ich in `budget_tab.py` gezielt auf Editierbarkeit der Parent-Zeilen und die Total-/Format-Logik mit Zeilenkontext.
collab spawn_agent(call_XMfJ221pMDkRcvP5HSLenVfR, prompt="Führe im Projektverzeichnis aus und berichte nur kurz Status + relevante Fehlerzeilen:
1) python -m compileall .
2) pyth…")
mcp startup: no servers
spawn_agent(call_XMfJ221pMDkRcvP5HSLenVfR, prompt="Führe im Projektverzeichnis aus und berichte nur kurz Status + relevante Fehlerzeilen:
1) python -m compileall .
2) pyth…") pending init:
  agent: 019cb33d-fc75-7032-b6ae-0e278b6801e9
exec
/usr/bin/zsh -lc "rg -n \"read-only|read only|ItemIsEditable|flags\\(|fmt_amount\\(|Total|Puffer|child|children|_parse_cell_amount|footer|TOTAL|setText\\(|setFlags\\(\" views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
49:def fmt_amount(val: float) -> str:
55:def _parse_cell_amount(text: str) -> float:
56:    """Parst eine Betrags-Zelle, auch im Format 'Kinder + Puffer' oder '1600.00+'."""
68:    - Leaf-Kategorien: editierbar (Monate + Total)
69:    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
70:      Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
73:    Footer (TOTAL): zählt **Leaf-Werte + Parent-Puffer** (keine Doppelzählung).
137:        # Bezeichnung + Fix + Wiederh. + Tag + 12 Monate + Total
237:                # Spalten: 0=Bezeichnung, 1=Fix, 2=∞, 3=Tag, 4-15=Monate, 16=Total
244:                    if next_c > 16:  # nach Total -> nächste Zeile
256:    def _is_footer_row(self, r: int) -> bool:
258:        return bool(it and it.text() == "TOTAL")
269:            if it and it.text() == "TOTAL":
326:    def _row_has_children(self, r: int) -> bool:
341:            name, depth, has_children, path
353:        has_children_name: dict[str, bool] = {}
354:        direct_children_by_name: dict[str, list[str]] = {}
360:            for ch in node["children"]:
366:            has_children_name[c.name] = bool(node["children"])
367:            direct_children_by_name[c.name] = [ch["cat"].name for ch in node["children"]]
codex
Ich sehe bereits potenzielle Spannungen im Code (Docstring vs. aktuelle Edit-Logik). Ich lese jetzt die relevanten Blöcke um die Treffer herum, um echte Regressionen von Absicht zu trennen.
exec
/usr/bin/zsh -lc "nl -ba views/tabs/budget_tab.py | sed -n '600,840p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "nl -ba views/tabs/budget_tab.py | sed -n '920,1125p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "nl -ba views/tabs/budget_tab.py | sed -n '1125,1385p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
   600	        self._buffer_cache.clear()
   601	
   602	        self._internal_change = True
   603	        try:
   604	            self.table.setRowCount(0)
   605	
   606	            # Budget-Saldo IMMER anzeigen (auch bei einzelnem Typ)
   607	            self._insert_total_row()
   608	            
   609	            for t in types:
   610	                matrix = self.budget.get_matrix(year, t)
   611	                flat, totals_by_name, buffer_by_name, direct_children_by_name = self._build_tree_flat(t, matrix)
   612	
   613	                # Buffer cache (für Footer + Parent-Puffer)
   614	                for name, own in buffer_by_name.items():
   615	                    self._buffer_cache[(t, name)] = dict(own)
   616	
   617	                # Typ-Header, wenn "Alle"
   618	                if typ == "Alle" and flat:
   619	                    r = self.table.rowCount()
 succeeded in 51ms:
   920	                d = self._row_depth(p)
   921	                if d == cur_depth - 1:
   922	                    parent_row = p
   923	                    break
   924	                p -= 1
   925	
   926	            if parent_row is None:
   927	                return
   928	
   929	            typ = self._row_typ(parent_row)
   930	            cat = self._row_cat_real(parent_row)
   931	            if not cat:
   932	                return
   933	
   934	            buf = float(self._buffer_cache.get((typ, cat), {}).get(logical_month, 0.0))
   935	            children_sum = self._sum_immediate_children_month(parent_row, month_col)
   936	            new_total = buf + children_sum
   937	
   938	            # Update cell
   939	            it = self.table.item(parent_row, month_col)
 succeeded in 51ms:
  1125	
  1126	        try:
  1127	            new_day = int(item.text())
  1128	            if new_day < 1 or new_day > 31:
  1129	                raise ValueError("Tag muss 1-31 sein")
  1130	        except Exception:
  1131	            self._internal_change = True
  1132	            item.setText(str(cat_obj.recurring_day or 1))
  1133	            self._internal_change = False
  1134	            QMessageBox.warning(self, tr("msg.info"), tr("msg.invalid_day"))
  1135	            return
  1136	
  1137	        self.cats.update_flags(cat_obj.id, is_fix=bool(cat_obj.is_fix), is_recurring=True, recurring_day=new_day)
  1138	
  1139	    def _handle_total_column_edit(self, item: QTableWidgetItem, r: int, typ: str, cat: str) -> None:
  1140	        """Spalte 16: Jahres-Total editiert → gleichmäßig auf 12 Monate verteilen."""
  1141	        try:
  1142	            total = parse_amount(item.text())
  1143	        except Exception:
  1144	            total = 0.0
collab wait(call_6k3aUvgnEquZ5EhpGeCLns78)
  receivers: 019cb33d-e063-7a81-bfff-792c86c605b3, 019cb33d-fc75-7032-b6ae-0e278b6801e9
codex
Ich prüfe kurz `utils.money.parse_money`, weil daran hängt, ob Werte wie `100.00+` korrekt in Totals einfließen oder still falsch berechnet werden.
codex
Ich führe jetzt beide Checks im Projektverzeichnis aus und melde danach nur den kurzen Status mit relevanten Fehlerzeilen.
exec
/usr/bin/zsh -lc "nl -ba utils/money.py | sed -n '1,220p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc 'python ai/i18n_check.py' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
     1	"""Zentrale Geld-Formatierung & Parsing für den Budgetmanager.
     2	
     3	Unterstützt CHF, EUR, USD und GBP.  Die aktive Währung wird über
     4	``set_currency()`` gesetzt (typischerweise beim App-Start aus den Settings)
     5	und von allen ``format_*``-Funktionen verwendet.
     6	
     7	Zahlenformat ist immer Schweizer-Stil: **1'234.56** (Apostroph als
     8	Tausender-Trenner, Punkt als Dezimalzeichen).
     9	"""
    10	
    11	from __future__ import annotations
    12	import logging
    13	logger = logging.getLogger(__name__)
    14	
    15	# ── Währungsdefinitionen ──────────────────────────────────────────────
    16	
    17	CURRENCIES: dict[str, dict] = {
    18	    "CHF": {"symbol": "CHF", "position": "suffix", "label": "CHF – Schweizer Franken"},
    19	    "EUR": {"symbol": "€",   "position": "suffix", "label": "EUR – Euro"},
    20	    "USD": {"symbol": "$",   "position": "prefix", "label": "USD – US-Dollar"},
exec
/usr/bin/zsh -lc 'python -m compileall .' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 50ms:
i18n key sync (flattened):
- de.json: total=1164 missing=0 extra=0
- en.json: total=1164 missing=0 extra=0
- fr.json: total=1148 missing=16 extra=0
  missing sample: ['create_user.btn_create', 'create_user.display_name_label', 'create_user.first_user_info', 'create_user.password_label', 'create_user.password_placeholder', 'create_user.password_repeat_placeholder', 'create_user.pin_label', 'create_user.pin_placeholder', 'create_user.pin_repeat_label', 'create_user.pin_repeat_placeholder']
 succeeded in 50ms:
Listing '.'...
Listing './.ai'...
Listing './.ai/dispatch'...
Listing './.ai/dispatch/20260302_151341'...
Listing './.ai/dispatch/20260302_152701'...
Listing './.ai/dispatch/20260302_152720'...
Listing './.ai/dispatch/20260302_162642'...
Listing './.ai/dispatch/20260303_112604'...
Listing './.claude'...
Listing './.claude/agent-memory'...
Listing './.claude/agent-memory/code-reviewer'...
Listing './.claude/agents'...
Listing './.claude/hooks'...
Listing './.claude/skills'...
Listing './.claude/skills/big'...
Listing './.claude/skills/do'...
Listing './.claude/skills/show-agents'...
Listing './.codex'...
Listing './.codex/agents'...
Listing './.gemini'...
codex
Status:
1) `python -m compileall .` → `OK` (Exit Code 0), keine Fehlerzeilen.
2) `python ai/i18n_check.py` → `OK` (Exit Code 0), aber i18n-Problem gefunden:

Relevante Zeilen:
- `- fr.json: total=1148 missing=16 extra=0`
- `missing sample: ['create_user.btn_create', 'create_user.display_name_label', 'create_user.first_user_info', 'create_user.password_label', 'create_user.password_placeholder', 'create_user.password_repeat_placeholder', 'create_user.pin_label', 'create_user.pin_placeholder', 'create_user.pin_repeat_label', 'create_user.pin_repeat_placeholder']`
wait(call_6k3aUvgnEquZ5EhpGeCLns78) 1 agents complete:
  019cb33d-fc75-7032-b6ae-0e278b6801e9 completed: "Status:
1) `python -m compileall .` → `OK` (Exit Code 0), keine Fehlerzeilen.
2) `python ai/i18n_check.py` → `OK` (Exit …"
codex
`compileall` ist sauber durchgelaufen. Ich warte noch auf das Reviewer-Ergebnis und schließe dann mit einem kurzen, präzisen Änderungsbericht ab.
collab wait(call_P9R2UVDfhir8bQyLKjIHAtdz)
  receivers: 019cb33d-e063-7a81-bfff-792c86c605b3
codex
Ich habe einen konkreten potenziellen Bug gefunden (Parsing von Parent-Markern in Recalc). Ich validiere noch kurz die Tree-Berechnung (`_build_tree_flat`), damit Severity und Auswirkung sauber belegt sind.
exec
/usr/bin/zsh -lc "nl -ba views/tabs/budget_tab.py | sed -n '300,410p'" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
   300	        """Gibt eine Farbe für den jeweiligen Typ zurück."""
   301	        m = getattr(self, "_type_colors", None) or {}
   302	        if typ in m:
   303	            return m[typ]
   304	        # Fallback auf normalisiertem DB-Key
   305	        from model.typ_constants import normalize_typ as _nt
   306	        if _nt(typ) == "Einkommen" and "Einkommen" in m:
   307	            return m["Einkommen"]
   308	        return QColor(ui_colors(self).neutral)
   309	
   310	    def _row_cat_real(self, r: int) -> str | None:
   311	        it0 = self.table.item(r, 0)
   312	        if not it0:
   313	            return None
   314	        v = it0.data(ROLE_CAT_REAL)
   315	        if v:
   316	            return str(v)
   317	        return None
   318	
   319	    def _row_depth(self, r: int) -> int:
codex
**Findings (priorisiert)**

1. **High**: Parent-`Total` kann nach Recalc falsch (oft `0.00+`) werden  
   - Datei: [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L1291)  
   - Kontext: In `_recalc_row_total()` wird für Parent-Zeilen über Monatszellen summiert mit `parse_amount(...)` ([L1291-L1294](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L1294)).  
   - Problem: Parent-Monatszellen enthalten Marker (`fmt_amount(total) + marker`, z. B. `100.00+`, siehe [L751](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L751), [L946](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L946)). `parse_money` liefert bei solchen Strings `0.0` statt Betrag ([utils/money.py:132-135](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/utils/money.py#L132)).  
   - Auswirkung: Anforderung „Total = Puffer + Kinder Anzeige“ kann nach Updates/Recalc regressieren, weil Jahres-Total auf Parent-Zeilen falsch berechnet wird.

2. **Low (Risiko/Inkonsistenz)**: Spezifikation im Code widerspricht aktuellem Verhalten  
   - Datei: [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L68)  
   - Kontext: Klassen-Doku sagt Parent-Monatszellen seien editierbar ([L69](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L69)), tatsächliche Logik blockiert Edits explizit ([L1086-L1088](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L1086)).  
   - Auswirkung: Höheres Regressionsrisiko bei späteren Änderungen (weil Kommentar und Implementierung auseinanderlaufen).

**Checks ohne Findings**

- `fmt_amount(0)` ist korrekt umgesetzt (`"0.00"`): [views/tabs/budget_tab.py:49-52](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py#L49)  
- Version `1.0.16` ist konsistent in beiden Dateien:  
  - [version.json:3](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/version.json#L3)  
  - [app_info.py:17](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/app_info.py#L17)
wait(call_P9R2UVDfhir8bQyLKjIHAtdz) 1 agents complete:
  019cb33d-e063-7a81-bfff-792c86c605b3 completed: "**Findings (priorisiert)**

1. **High**: Parent-`Total` kann nach Recalc falsch (oft `0.00+`) werden  
   - Datei: [view…"
codex
Der Reviewer hat einen echten High-Issue gefunden (Parent-Recalc mit `+`-Marker). Ich setze jetzt einen minimalen Nachfix in `budget_tab.py` und laufe anschließend `compileall` erneut kurz drüber.
exec
/usr/bin/zsh -lc "rg -n \"def _recalc_row_total|fmt_amount\\(|marker|parse_amount|Parent\" views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
45:def parse_amount(text: str) -> float:
49:def fmt_amount(val: float) -> str:
59:        return sum(parse_amount(p) for p in raw.split(" + "))
60:    return parse_amount(raw)
69:    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
71:    - Parent ohne Children: wie Leaf (normales Budgetverhalten)
73:    Footer (TOTAL): zählt **Leaf-Werte + Parent-Puffer** (keine Doppelzählung).
530:                    it.setText(fmt_amount(saldo))
541:                        f"{tr('kpi.income')}:   {fmt_amount(ein)}\n"
542:                        f"{tr('kpi.expenses')}:    {fmt_amount(aus)}\n"
543:                        f"{tr('typ.Ersparnisse')}:  {fmt_amount(ers)}\n"
545:                        f"{tr('lbl.saldo')}:       {fmt_amount(saldo)}"
556:                it_total.setText(fmt_amount(jahr_saldo))
566:                    f"{tr('lbl.annual_income')}:   {fmt_amount(jahr_ein)}\n"
567:                    f"{tr('lbl.annual_expenses')}:    {fmt_amount(jahr_aus)}\n"
568:                    f"{tr('lbl.annual_savings')}:  {fmt_amount(jahr_ers)}\n"
570:                    f"{tr('lbl.annual_balance')}:       {fmt_amount(jahr_saldo)}"
613:                # Buffer cache (für Footer + Parent-Puffer)
751:                            _pm = tr("budget.parent.marker")
752:                            _cell_text = f"{fmt_amount(total_val)}{_pm}"
exec
/usr/bin/zsh -lc "sed -n '1,90p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3

from PySide6.QtCore import Qt, QEvent, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog,
    QMenu, QInputDialog
)

from utils.i18n import tr, trf
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, is_income
from utils.i18n import display_typ, db_typ_from_display, tr_category_name
from model.category_model import CategoryModel, Category
from model.budget_model import BudgetModel
from model.favorites_model import FavoritesModel
from model.budget_warnings_model_extended import BudgetWarningsModelExtended
exec
/usr/bin/zsh -lc "sed -n '1268,1355p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
            val = abs(val)
            QMessageBox.information(self, tr("msg.info"), tr("msg.negative_not_allowed"))

        self._internal_change = True
        try:
            item.setText(fmt_amount(val))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        finally:
            self._internal_change = False

        self._recalc_row_total(r)
        if 4 <= c <= 15:
            self._update_parent_chain(r, c)
        self._recalc_footer()

        if self.chk_autosave.isChecked() and (4 <= c <= 15):
            self._persist_single_cell(r, c)

    def _recalc_row_total(self, r: int):
        data_rows = self._row_count_data()
codex
Ich mache jetzt einen kleinen Nachpatch: `_recalc_row_total` nutzt künftig den robusten Zellparser (inkl. `+`-Marker), und ich gleiche die Klassen-Doku auf „Parent-Monate read-only“ an.
file update
M /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager/views/tabs/budget_tab.py
@@ -68,3 +68,3 @@
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
@@ -1298,3 +1298,3 @@
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
apply_patch(auto_approved=true) exited 0 in 9ms:
Success. Updated the following files:
M views/tabs/budget_tab.py
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..17f18135795867ca276215ae2f1910ddaa7ce068
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -1296,7 +1296,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..17f18135795867ca276215ae2f1910ddaa7ce068
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -1296,7 +1296,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

codex
Ich verifiziere den Nachpatch jetzt nochmal mit `compileall` und dem i18n-Check, damit der Zustand konsistent bleibt.
collab spawn_agent(call_fCN9Et09tmVqWGRs0Fc73j9U, prompt="Bitte im Projektverzeichnis ausführen und kurz zusammenfassen:
1) python -m compileall .
2) python ai/i18n_check.py")
spawn_agent(call_fCN9Et09tmVqWGRs0Fc73j9U, prompt="Bitte im Projektverzeichnis ausführen und kurz zusammenfassen:
1) python -m compileall .
2) python ai/i18n_check.py") not found:
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..17f18135795867ca276215ae2f1910ddaa7ce068
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -1296,7 +1296,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

collab close_agent(call_ArF5MZp3SC77ko9ZGjgkt1gS)
  receiver: 019cb33b-f0a4-7972-bea0-e0117aa9b1f5
close_agent(call_ArF5MZp3SC77ko9ZGjgkt1gS) completed: "Relevante Dateien (gezielt geprüft):
- [views/tabs/budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/G…":
  receiver: 019cb33b-f0a4-7972-bea0-e0117aa9b1f5
collab close_agent(call_z3qXcOJyZz9BlSkuDmt2uq5p)
  receiver: 019cb33c-e147-7931-a255-47594da1364b
close_agent(call_z3qXcOJyZz9BlSkuDmt2uq5p) completed: "Umgesetzt, minimal-invasiv und ohne Tests auszuführen.

Geänderte Stellen:

- `fmt_amount(0)` zeigt jetzt `0.00` statt l…":
  receiver: 019cb33c-e147-7931-a255-47594da1364b
collab close_agent(call_OZcyn3RlTx9EA2fZ2pRXwsXT)
  receiver: 019cb33d-e063-7a81-bfff-792c86c605b3
close_agent(call_OZcyn3RlTx9EA2fZ2pRXwsXT) completed: "**Findings (priorisiert)**

1. **High**: Parent-`Total` kann nach Recalc falsch (oft `0.00+`) werden  
   - Datei: [view…":
  receiver: 019cb33d-e063-7a81-bfff-792c86c605b3
collab close_agent(call_Tj0Dl7SMoNJQ8z05Jh26toGr)
  receiver: 019cb33d-fc75-7032-b6ae-0e278b6801e9
close_agent(call_Tj0Dl7SMoNJQ8z05Jh26toGr) completed: "Status:
1) `python -m compileall .` → `OK` (Exit Code 0), keine Fehlerzeilen.
2) `python ai/i18n_check.py` → `OK` (Exit …":
  receiver: 019cb33d-fc75-7032-b6ae-0e278b6801e9
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..17f18135795867ca276215ae2f1910ddaa7ce068
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -1296,7 +1296,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

collab spawn_agent(call_MjEUQl12VbJOPBJru6BrmgMK, prompt="Führe im Projektverzeichnis aus und gib nur kurze Ergebniszeilen zurück:
1) python -m compileall .
2) python ai/i18n_che…")
spawn_agent(call_MjEUQl12VbJOPBJru6BrmgMK, prompt="Führe im Projektverzeichnis aus und gib nur kurze Ergebniszeilen zurück:
1) python -m compileall .
2) python ai/i18n_che…") pending init:
  agent: 019cb33f-258a-74d1-86bd-e26a5c25a7dc
mcp startup: no servers
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..17f18135795867ca276215ae2f1910ddaa7ce068
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -1296,7 +1296,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

codex
Ich führe jetzt beide Prüfkommandos im Projektverzeichnis aus und melde anschließend nur kurze Ergebniszeilen.
exec
/usr/bin/zsh -lc 'python ai/i18n_check.py' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc 'python -m compileall .' in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 50ms:
i18n key sync (flattened):
- de.json: total=1164 missing=0 extra=0
- en.json: total=1164 missing=0 extra=0
- fr.json: total=1148 missing=16 extra=0
  missing sample: ['create_user.btn_create', 'create_user.display_name_label', 'create_user.first_user_info', 'create_user.password_label', 'create_user.password_placeholder', 'create_user.password_repeat_placeholder', 'create_user.pin_label', 'create_user.pin_placeholder', 'create_user.pin_repeat_label', 'create_user.pin_repeat_placeholder']
 succeeded in 50ms:
Listing '.'...
Listing './.ai'...
Listing './.ai/dispatch'...
Listing './.ai/dispatch/20260302_151341'...
Listing './.ai/dispatch/20260302_152701'...
Listing './.ai/dispatch/20260302_152720'...
Listing './.ai/dispatch/20260302_162642'...
Listing './.ai/dispatch/20260303_112604'...
Listing './.claude'...
Listing './.claude/agent-memory'...
Listing './.claude/agent-memory/code-reviewer'...
Listing './.claude/agents'...
Listing './.claude/hooks'...
Listing './.claude/skills'...
Listing './.claude/skills/big'...
Listing './.claude/skills/do'...
Listing './.claude/skills/show-agents'...
Listing './.codex'...
Listing './.codex/agents'...
Listing './.gemini'...
collab wait(call_WTbAzC6cnhBN0nlxjYmkAXvC)
  receivers: 019cb33f-258a-74d1-86bd-e26a5c25a7dc
codex
1) `python -m compileall .` → OK (Exit Code 0)  
2) `python ai/i18n_check.py` → OK (Exit Code 0), aber `fr.json`: `missing=16`, `extra=0`
wait(call_WTbAzC6cnhBN0nlxjYmkAXvC) 1 agents complete:
  019cb33f-258a-74d1-86bd-e26a5c25a7dc completed: "1) `python -m compileall .` → OK (Exit Code 0)  
2) `python ai/i18n_check.py` → OK (Exit Code 0), aber `fr.json`: `missi…"
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..63409f0f0cd2f141bc88d605b6c88e4a374dad8f
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -785,7 +785,8 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
+                        _puffer_year = max(0.0, row_buf_total)
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {_puffer_year:.2f}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -795,9 +796,9 @@
                         )
                         tot_lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_year_sum)}"]
                         tot_tip = "\n".join(tot_lines)
-                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien
+                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien (nicht editierbar)
                         tot_marker = tr("budget.parent.marker")
-                        tot_text = f"{fmt_amount(row_total)}{tot_marker}"
+                        tot_text = f"{row_display_total:.2f}{tot_marker}"
                     else:
                         tot_tip = path
                         tot_text = fmt_amount(row_total)
@@ -1296,7 +1297,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

codex
Der Nachcheck ist erfolgreich (Compile OK). Ich verifiziere noch kurz die finalen Stellen in den Dateien und gebe dir dann das knappe Abschlussprotokoll.
exec
/usr/bin/zsh -lc "rg -n \"def fmt_amount|Parent mit Children|_recalc_row_total|_parse_cell_amount\\(|setFlags\\(it.flags\\(\\) & ~Qt.ItemIsEditable\\)|has_children and 4 <= c <= 15|APP_VERSION|\\\"version\\\"\" views/tabs/budget_tab.py app_info.py version.json" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManagerexec
/usr/bin/zsh -lc "sed -n '740,815p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 50ms:
version.json:3:  "version": "1.0.16"
app_info.py:17:APP_VERSION = "1.0.16"
app_info.py:25:    return f"{APP_NAME} v{APP_VERSION}"
app_info.py:30:    return f"Über {APP_NAME} v{APP_VERSION}"
app_info.py:35:    return f"{APP_VERSION} ({APP_RELEASE_DATE})"
views/tabs/budget_tab.py:49:def fmt_amount(val: float) -> str:
views/tabs/budget_tab.py:55:def _parse_cell_amount(text: str) -> float:
views/tabs/budget_tab.py:69:    - Parent mit Children: Monatszellen read-only.
views/tabs/budget_tab.py:764:                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
views/tabs/budget_tab.py:810:                    # Total-Spalte: Parent mit Children -> read-only
views/tabs/budget_tab.py:848:        display_val = _parse_cell_amount(it_self.text() if it_self else "")
views/tabs/budget_tab.py:862:                ch_val = _parse_cell_amount(it.text() if it else "")
views/tabs/budget_tab.py:896:                total += _parse_cell_amount(it.text() if it else "")
views/tabs/budget_tab.py:959:            self._recalc_row_total(parent_row)
views/tabs/budget_tab.py:1048:        # Bei Parent mit Children: amt ist Display (buffer+children) -> wir speichern NUR buffer
views/tabs/budget_tab.py:1094:        if has_children and 4 <= c <= 15:
views/tabs/budget_tab.py:1179:        self._recalc_row_total(r)
views/tabs/budget_tab.py:1228:        self._recalc_row_total(r)
views/tabs/budget_tab.py:1279:        self._recalc_row_total(r)
views/tabs/budget_tab.py:1287:    def _recalc_row_total(self, r: int):
exec
/usr/bin/zsh -lc "sed -n '1078,1100p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
                    row_buf_total = 0.0
                    row_child_total = 0.0
                    row_display_total = 0.0  # klammerter Anzeigewert (max(0,buf)+kinder)
                    for m in range(1, 13):  # m = logischer Monat (1-12)
                        col_idx = m + 3  # Spalte 4-15 (wegen Fix/Wiederkehrend/Tag davor)

                        total_val = float(totals_by_name.get(name, {}).get(m, 0.0))
                        own_val   = float(buffer_by_name.get(name, {}).get(m, 0.0))
                        child_val = float(total_val - own_val)

                        if has_children:
                            _pm = tr("budget.parent.marker")
                            # Negativen Buffer ignorieren: Anzeigewert = max(0, puffer) + kinder
                            _children_m = total_val - own_val
                            _display_m = max(0.0, own_val) + _children_m
                            _cell_text = f"{_display_m:.2f}{_pm}"
                            row_display_total += _display_m
                        else:
                            _cell_text = fmt_amount(total_val)
                            row_display_total += total_val
 succeeded in 50ms:
        # Spalte 3: Tag (recurring_day)
        if c == 3:
            self._handle_recurring_day_edit(item, r)
            return

        typ = self._row_typ(r)
        cat = self._row_cat_real(r)
        if not cat:
            return

        has_children = self._row_has_children(r)

        # Parent + Children: Total-Spalte ist read-only
        if has_children and c == 16:
            return
        # Parent + Children: Monatszellen sind read-only (Buffer wird nicht direkt im Grid editiert)
        if has_children and 4 <= c <= 15:
            return

        # Total-Spalte → auf Monate verteilen (nur Leaf)
exec
/usr/bin/zsh -lc "sed -n '1284,1342p' views/tabs/budget_tab.py" in /home/sloogy/Projekt/Project Phython/Budgetmanager/GPT/Testing/CLI_AI driven-dev/BudgetManager succeeded in 51ms:
        if self.chk_autosave.isChecked() and (4 <= c <= 15):
            self._persist_single_cell(r, c)

    def _recalc_row_total(self, r: int):
        data_rows = self._row_count_data()
        if r >= data_rows:
            return
        if self._is_header_row(r):
            return
        if self._is_total_row(r):
            return  # Total-Zeile wird separat berechnet
        has_children = self._row_has_children(r)

        row_total = 0.0
        for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
            it = self.table.item(r, col_idx)
            row_total += _parse_cell_amount(it.text() if it else "")

        tot = self.table.item(r, 16)  # Spalte 16 (Total)
        if tot is None:
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..63409f0f0cd2f141bc88d605b6c88e4a374dad8f
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -785,7 +785,8 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
+                        _puffer_year = max(0.0, row_buf_total)
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {_puffer_year:.2f}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -795,9 +796,9 @@
                         )
                         tot_lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_year_sum)}"]
                         tot_tip = "\n".join(tot_lines)
-                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien
+                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien (nicht editierbar)
                         tot_marker = tr("budget.parent.marker")
-                        tot_text = f"{fmt_amount(row_total)}{tot_marker}"
+                        tot_text = f"{row_display_total:.2f}{tot_marker}"
                     else:
                         tot_tip = path
                         tot_text = fmt_amount(row_total)
@@ -1296,7 +1297,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

collab close_agent(call_vRloBLmiLXdauO3wPK3ORiii)
  receiver: 019cb33f-258a-74d1-86bd-e26a5c25a7dc
close_agent(call_vRloBLmiLXdauO3wPK3ORiii) completed: "1) `python -m compileall .` → OK (Exit Code 0)  
2) `python ai/i18n_check.py` → OK (Exit Code 0), aber `fr.json`: `missi…":
  receiver: 019cb33f-258a-74d1-86bd-e26a5c25a7dc
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..6f08c5d6c35ef7be261c2a0e43fd63b2d43b4ff2
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -785,7 +785,8 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
+                        _puffer_year = max(0.0, row_buf_total)
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {_puffer_year:.2f}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -795,9 +796,9 @@
                         )
                         tot_lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_year_sum)}"]
                         tot_tip = "\n".join(tot_lines)
-                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien
+                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien (nicht editierbar)
                         tot_marker = tr("budget.parent.marker")
-                        tot_text = f"{fmt_amount(row_total)}{tot_marker}"
+                        tot_text = f"{row_display_total:.2f}{tot_marker}"
                     else:
                         tot_tip = path
                         tot_text = fmt_amount(row_total)
@@ -939,7 +940,8 @@
 
             buf = float(self._buffer_cache.get((typ, cat), {}).get(logical_month, 0.0))
             children_sum = self._sum_immediate_children_month(parent_row, month_col)
-            new_total = buf + children_sum
+            # Negativen Buffer ignorieren: Anzeigewert = max(0, puffer) + kinder
+            display_total = max(0.0, buf) + children_sum
 
             # Update cell
             it = self.table.item(parent_row, month_col)
@@ -949,8 +951,9 @@
             self._internal_change = True
             try:
                 _pm = tr("budget.parent.marker")
-                it.setText(f"{fmt_amount(new_total)}{_pm}")
+                it.setText(f"{display_total:.2f}{_pm}")
                 it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
+                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                 it.setToolTip(self._build_parent_tooltip(parent_row, month_col))
             finally:
                 self._internal_change = False
@@ -1296,7 +1299,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

codex
Umgesetzt mit Rollenfolge `explorer -> worker -> reviewer`, danach Nachfix aus Reviewer-Finding.

Änderungen (minimal):
- Parent-Monatszellen sind read-only (UI + Guard in Change-Handler):  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:764), [budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:1094)
- `fmt_amount(0)` gibt jetzt `0.00` zurück:  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:49)
- Parent-Total-Anzeige bleibt `Puffer + Kinder` (Marker) und Recalc wurde robust gefixt:  
`_recalc_row_total` summiert nun mit `_parse_cell_amount(...)` (verarbeitet Marker wie `100.00+` korrekt), damit kein `0.00+`-Regression:  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:1300)
- Doku im Klassenkommentar auf read-only-Verhalten angepasst:  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:69)
- Version auf `1.0.16`:  
[version.json](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/version.json:3), [app_info.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/app_info.py:17)

Checks:
- `python -m compileall .` -> OK
- `python ai/i18n_check.py` -> OK, aber bestehender Befund: `fr.json missing=16` (nicht durch diese Änderung verursacht)
file update:
diff --git a/views/tabs/budget_tab.py b/views/tabs/budget_tab.py
index 4be8337b1400a0e68d76d19713b4b0c772992f42..d7f391438cddbe01151dd1df0b75e09fe989c44a
--- a/views/tabs/budget_tab.py
+++ b/views/tabs/budget_tab.py
@@ -66,7 +66,7 @@
 
     Regeln:
     - Leaf-Kategorien: editierbar (Monate + Total)
-    - Parent mit Children: Monatszellen editierbar als **Puffer** (Eigenbetrag).
+    - Parent mit Children: Monatszellen read-only.
       Anzeige = Puffer + Summe(Children). Total-Spalte ist read-only.
     - Parent ohne Children: wie Leaf (normales Budgetverhalten)
 
@@ -785,7 +785,8 @@
 
                     if has_children:
                         ch_names = direct_children_by_name.get(name, [])
-                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(row_buf_total)}", _SEP]
+                        _puffer_year = max(0.0, row_buf_total)
+                        tot_lines = [f"{tr('budget.tooltip.puffer')}:  {_puffer_year:.2f}", _SEP]
                         for ch in ch_names:
                             ch_year = sum(float(totals_by_name.get(ch, {}).get(mm, 0.0)) for mm in range(1, 13))
                             tot_lines.append(f"  {tr_category_name(ch)}:  {fmt_amount(ch_year)}")
@@ -795,9 +796,9 @@
                         )
                         tot_lines += [_SEP, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(ch_year_sum)}"]
                         tot_tip = "\n".join(tot_lines)
-                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien
+                        # "+" Marker zeigt: Wert ist Summe aus Unterkategorien (nicht editierbar)
                         tot_marker = tr("budget.parent.marker")
-                        tot_text = f"{fmt_amount(row_total)}{tot_marker}"
+                        tot_text = f"{row_display_total:.2f}{tot_marker}"
                     else:
                         tot_tip = path
                         tot_text = fmt_amount(row_total)
@@ -864,9 +865,10 @@
             i += 1
 
         children_sum = sum(v for _, v in children)
-        puffer_val = display_val - children_sum
+        # Puffer = was die Zelle anzeigt minus Kinder, mindestens 0
+        puffer_val = max(0.0, display_val - children_sum)
         sep = "─" * 28
-        lines = [f"{tr('budget.tooltip.puffer')}:  {fmt_amount(puffer_val)}", sep]
+        lines = [f"{tr('budget.tooltip.puffer')}:  {puffer_val:.2f}", sep]
         for ch_name, ch_val in children:
             lines.append(f"  {ch_name}:  {fmt_amount(ch_val)}")
         lines += [sep, f"{tr('budget.tooltip.children_sum')}:  {fmt_amount(children_sum)}"]
@@ -939,7 +941,8 @@
 
             buf = float(self._buffer_cache.get((typ, cat), {}).get(logical_month, 0.0))
             children_sum = self._sum_immediate_children_month(parent_row, month_col)
-            new_total = buf + children_sum
+            # Negativen Buffer ignorieren: Anzeigewert = max(0, puffer) + kinder
+            display_total = max(0.0, buf) + children_sum
 
             # Update cell
             it = self.table.item(parent_row, month_col)
@@ -949,8 +952,9 @@
             self._internal_change = True
             try:
                 _pm = tr("budget.parent.marker")
-                it.setText(f"{fmt_amount(new_total)}{_pm}")
+                it.setText(f"{display_total:.2f}{_pm}")
                 it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
+                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                 it.setToolTip(self._build_parent_tooltip(parent_row, month_col))
             finally:
                 self._internal_change = False
@@ -1296,7 +1300,7 @@
         row_total = 0.0
         for col_idx in range(4, 16):  # Spalten 4-15 (Jan-Dez)
             it = self.table.item(r, col_idx)
-            row_total += parse_amount(it.text() if it else "")
+            row_total += _parse_cell_amount(it.text() if it else "")
 
         tot = self.table.item(r, 16)  # Spalte 16 (Total)
         if tot is None:

tokens used
37'888
Umgesetzt mit Rollenfolge `explorer -> worker -> reviewer`, danach Nachfix aus Reviewer-Finding.

Änderungen (minimal):
- Parent-Monatszellen sind read-only (UI + Guard in Change-Handler):  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:764), [budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:1094)
- `fmt_amount(0)` gibt jetzt `0.00` zurück:  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:49)
- Parent-Total-Anzeige bleibt `Puffer + Kinder` (Marker) und Recalc wurde robust gefixt:  
`_recalc_row_total` summiert nun mit `_parse_cell_amount(...)` (verarbeitet Marker wie `100.00+` korrekt), damit kein `0.00+`-Regression:  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:1300)
- Doku im Klassenkommentar auf read-only-Verhalten angepasst:  
[budget_tab.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/views/tabs/budget_tab.py:69)
- Version auf `1.0.16`:  
[version.json](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/version.json:3), [app_info.py](/home/sloogy/Projekt/Project%20Phython/Budgetmanager/GPT/Testing/CLI_AI%20driven-dev/BudgetManager/app_info.py:17)

Checks:
- `python -m compileall .` -> OK
- `python ai/i18n_check.py` -> OK, aber bestehender Befund: `fr.json missing=16` (nicht durch diese Änderung verursacht)
