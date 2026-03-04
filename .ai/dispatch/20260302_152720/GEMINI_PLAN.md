Loaded cached credentials.
I will start by identifying the files responsible for overview charts and widgets and searching for hardcoded strings or string-based logic in those files.
I will search for "Chart" and "Plot" in the `views/` directory to locate the files responsible for rendering overview charts and dashboards.
I will read `views/tabs/overview_kpi_panel.py` and `views/tabs/overview_tab.py` to identify hardcoded strings and string-based comparisons that could cause issues in English and French locales.
I will read `views/tabs/overview_widgets.py` to understand how the `slice_clicked` signal is emitted and what data it carries, which will help me refactor the matching logic to use stable keys.
I will read `views/tabs/overview_right_panel.py` to identify any similar issues with string-based matching or hardcoded UI elements.
I will read `views/tabs/overview_tab.py` to understand the orchestration between the panels and identify any additional hardcoded strings or language-dependent logic.
I will list the files in `views/tabs/` to ensure no other relevant files have been missed.
I will read `views/tabs/overview_budget_panel.py` to check for any additional hardcoded strings or language-dependent chart logic.
I will read `model/typ_constants.py` to identify the available constants for income, expenses, and savings, ensuring they are used correctly in the refactoring process.
I will now write the plan and i18n checklist for fixing the overview charts and widgets to `SUMMARY.md`.
Error executing tool write_file: Tool "write_file" not found. Did you mean one of: "read_file", "cli_help", "activate_skill"?
I will use the `cli_help` tool to ask about the available tools for writing files and running shell commands, as they were mentioned in the system prompt but are not in the tool declarations.
Error executing tool cli_help: Subagent Failed: cli_help
Error: The operation was aborted.
I will try to use `run_shell_command` to write the plan and checklist to `SUMMARY.md`, as it was mentioned in the system prompt despite not being in the tool declarations.
Error executing tool run_shell_command: Tool "run_shell_command" not found. Did you mean one of: "grep_search", "cli_help", "read_file"?
I will use the `cli_help` tool to ask about the missing `write_file` and `run_shell_command` tools, as I need them to fulfill the user's request.
Error executing tool cli_help: Subagent Failed: cli_help
Error: The operation was aborted.
I will use the `list_directory` tool to see if `SUMMARY.md` exists and where it is located.
I will read the current content of `SUMMARY.md` to see its status and what has been documented so far.
I will use the `cli_help` tool to ask about the `write_file` tool and how to use it, as I need to modify `SUMMARY.md` to complete the task.
Error executing tool cli_help: Subagent Failed: cli_help
Error: The operation was aborted.
I will use the `codebase_investigator` tool to analyze the current state of the overview charts and widgets, as requested in the task.
I will read `.gemini/settings.json` to check if there is any configuration that explains why the `write_file` or `run_shell_command` tools are missing.
I will use the `grep_search` tool to find all occurrences of `db_typ_from_display()` in the codebase to confirm the language-dependent logic and key-based comparison issues.
I will use the `codebase_investigator` tool again with a narrower objective to analyze the specific issues in the overview charts and widgets, aiming for a more focused and successful report.
Error executing tool codebase_investigator: Subagent Failed: codebase_investigator
Error: The operation was aborted.
I have analyzed the current state of the overview charts and widgets and identified several issues related to hardcoded strings and language-dependent logic. Due to the absence of file-modification tools in my current environment, I am providing the required plan and i18n checklist here.

### Plan & i18n-Checkliste: Fix Übersichts-Charts/Widgets (codex2)

#### 1. Analyse & Ist-Zustand (Research)
- **Problem**: `OverviewKpiPanel` nutzt `display_typ()` (lokalisiert) für Chart-Klicks (`raw_label`). In EN/FR schlägt die Rück-Übersetzung `db_typ_from_display()` fehl, wenn der String nicht exakt passt.
- **Problem**: `OverviewRightPanel` und `OverviewBudgetPanel` vergleichen Combo-Box-Texte statt `userData`.
- **Problem**: Hardcodierte UI-Strings (z. B. "Min", "Max", "Beschreibung", "Transaktionen") in Sidebars und Tabellen-Headern.

#### 2. Strategie & Implementierung (Execution)
- **Stabile Keys statt Display-Text**:
    - **OverviewKpiPanel**: `refresh_charts()` setzt `raw_label` auf `TYP_INCOME`, `TYP_EXPENSES` oder `TYP_SAVINGS` (Konstanten aus `model.typ_constants`).
    - **OverviewKpiPanel**: `_on_donut_clicked()` wertet den Key direkt aus (kein `db_typ_from_display`).
    - **OverviewRightPanel**: `typ_combo` mit `addItem(display, key)` befüllen; `currentData()` für Filter-Logik nutzen.
    - **OverviewBudgetPanel**: `bo_typ_combo` analog auf `currentData()` umstellen.
- **i18n-Fixes (Hardcoded Strings)**:
    - **OverviewRightPanel**: "Min", "Max", "Beschreibung...", "Transaktionen" durch `tr("lbl.min")`, `tr("lbl.max")`, `tr("lbl.description")` und `trf("overview.count.transactions", n=x)` ersetzen.
    - **OverviewBudgetPanel**: `is_income(typ_db)` statt hardcodierter String-Checks (`"income"`, `"einnahmen"`) nutzen.
    - **OverviewBudgetPanel**: Zeilenbeschriftungen in der Budget-Tabelle (Tab 3) lokalisieren.
- **Sprachunabhängigkeit**:
    - Alle Signal-Emitter (`kpi_clicked`, `typ_filter_changed`) senden nur noch stabile DB-Keys oder `None` (für "Alle").
    - `normalize_typ()` konsequent nutzen, um Aliase abzufangen.

#### 3. i18n-Checkliste (Validation)
- [ ] **Keys prüfen**: `lbl.min`, `lbl.max`, `lbl.description`, `tab.filter`, `tab.transactions` in `de.json`, `en.json`, `fr.json` ergänzen.
- [ ] **Placeholder**: Sicherstellen, dass `trf()`-Parameter (z. B. `{n}`) in allen Sprachen identisch sind.
- [ ] **Kompilierung**: `python -m compileall .` (Syntax-Check).
- [ ] **Tool-Check**: `python ai/i18n_check.py` (Sync-Check der Keys).

#### 4. Finalisierung
- Ergebnisbericht und Fix-Status in `SUMMARY.md` dokumentieren.
