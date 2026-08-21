# BudgetManager 2.2.70 – User guide

This guide describes the functions actually available in version 2.2.70. BudgetManager stores data locally, never books without confirmation, and separates **budget (plan)** from **tracking (real transactions)**.

## First start in four steps

1. Choose language, currency and number format.
2. Create an account and store the restore key separately.
3. Prepare categories through Express setup, XLSX import or manual editing.
4. Record the first transaction, then use budgets or tracking learning mode.

## 1. Quick start

1. Choose language, currency and number format.
2. Create a Quick, PIN or password account.
3. Store the restore key outside the application folder.
4. Use Express setup or create categories yourself.
5. Enter budgets or start with tracking learning mode.
6. Follow the cockpit’s next steps.

## 2. Main areas

The left sidebar opens Cockpit, Tracking, Budget, Savings goals, Overview, optional Categories and Account. The action toolbar gives one consistent entry point for add transaction, book fixed/recurring, categories, savings and search.

## 3. Categories

Every category belongs to income, expenses or savings and may be a parent or child. Children can only move within the same type.

Properties include fixed cost, recurring, due day, forecast mode (Auto, Normal/Flexible, Pot/Reserve, Incremental), favorite and fixed tags. Renaming cascades through budgets, tracking, favorites, warnings, recurring data and savings goals. Deletion can remove dependent data or reassign it; create a backup first.

The setup assistant can import an XLSX category template. Daily management uses **Ctrl+K**.

## 4. Budget

Budgets are planned values and do not create transactions. Enter one month, all months or a range, optionally only into empty cells.

**Copy year** selects source/target year, all accounts or one type, amounts on/off and a per-category review list. Fixed, recurring, pot, incremental and learning items are reviewed. The **13th salary** button creates a one-time income budget in exactly one payout month.

Forecasts use completed months and stable patterns; nothing is applied automatically.

## 5. Forecast modes and learning

- **Normal/Flexible:** everyday variable spending.
- **Pot/Reserve:** expected irregular costs such as deductibles, repairs or annual invoices. Partial use does not reduce the pot automatically; an overrun can trigger an increase warning.
- **Incremental:** annual or quarterly costs paid irregularly or in parts.
- **Tracking learning mode:** proposes starting budgets only where no positive annual budget exists. Configure first proposal, stable months, current-month projection, report visibility and auto end under **File → Settings → Behaviour → Budget overview**.
- **Soft Zero Budget:** checks **income − expenses − savings ≈ CHF 0**. It proposes savings/carryover for a surplus and savings then flexible expenses for a deficit. Fixed, recurring, pot and incremental costs remain protected.

A pot is an expected expense reserve. A savings goal has a fixed target with deposits and withdrawals.

## 5.1 Choosing a forecast mode

Use Normal/Flexible for everyday spending, Pot/Reserve for expected irregular costs, Incremental for staged annual costs, and learning mode only when a category has no positive annual budget.

## 6. Transactions / tracking

A transaction contains date, account/type, category, amount, note and tags. **Ctrl+N** opens the same full dialog from cockpit, toolbar and Tracking. Save and add another keeps useful choices such as the account.

Edit, duplicate or delete through buttons/context menu. **Ctrl+Shift+F** lists due fixed, recurring and expected items for a selected month and books only checked rows.

Filters combine type/account, category including descendants, tags, date range, amount and free text. Reset restores all rows. Savings transactions can update linked goals; withdrawals are explicitly confirmed.

A **Fixed cost** is protected from flexible reduction hints.

## 7. Overview

Choose year, month or custom range and combine filters for account/type, category including children, tags, note and amount. The Overview contains KPI cards, planned/actual tables, remaining amount, percentage, overruns, filtered transactions and reviewed suggestions.

### Chart guide

Charts include planned/actual donut, category ranking, type comparison, monthly trend, balance trend and top transactions. Clicking cards/charts applies filters; double-clicking a budget row opens its editor.

## 8. Savings goals

Savings goals are project cash flows. The app shows **target**, **contributed**, **used/withdrawn**, **current stock**, and **still to contribute** separately. Example: target `50,000`, contributed `30,000`, used `15,000` means stock `15,000` and `20,000` still to contribute. A negative savings transaction defaults to **withdrawal**. Choose **correction** explicitly for an erroneous booking so it does not count as project use. **Partial release** makes a selected amount available while the goal remains active.

## 9. Cockpit

The cockpit shows traffic light, next steps, KPIs, due items, warnings, pot balances, favorites, goals and recent transactions. Customise card visibility and order.

### 9.1 Key figures and trend

The four tiles at the top show income, expenses, savings and the free amount. The bottom right of each tile compares against the previous month as an arrow with an amount. The colour follows meaning rather than sign: more income is green, more spending is red. In the very first month the arrow stays hidden.

### 9.2 Insights

The **Insights** section holds two charts. The ring shows this month's spending per category with the total in the centre; more than five categories are folded into a remainder slice. The area chart beside it shows cumulative spending across the month, making it visible whether spending clusters at the start or the end.

### 9.3 Automatic or pinned layout

The default is **automatic**: sections without content shrink to their header and drop below the filled ones. Once a section has content again it returns to its stored position.

For your own arrangement enable **View → Cockpit layout → Arrange tiles freely** or the matching switch at the top of the cockpit. The **entire header** of each tile then becomes a drag zone; the `≡` handle remains available as well. The left and right columns are independent stacks, so a right-hand tile can move all the way to the top regardless of tile heights on the left. A highlighted **drop placeholder** shows the exact destination while dragging. Order and column are saved as soon as you drop the tile. Tables, buttons, and charts inside the tile remain fully interactive because the content area itself is not draggable. **View → Cockpit layout → Reset cockpit layout** restores automatic mode, the default order, and the default columns.

Both at once is deliberately impossible: automatic sorting would overwrite a hand-made arrangement on the next refresh.

### 9.4 One or two columns

In automatic mode the cockpit switches to two columns at roughly 1180 pixels. In manual mode two equal target columns are available from 720 pixels so tiles can be moved freely between left and right at normal window sizes. At even narrower widths the surrounding view may scroll horizontally while preserving the saved arrangement.

### 9.5 Appearance

Colours and tile shapes come entirely from the active design profile. **Settings → Appearance** offers 26 profiles and lets you create your own. **Midnight – Violet** matches the modern dashboard look: near-black background, raised tiles, violet accent.

## 10. Tags

Tags add context beyond categories. Fixed category tags are added automatically; manual tags remain when the category changes.

## 11. Accounts

BudgetManager always keeps the three base account types **Income**, **Expenses** and **Savings**. Additional accounts can be created, colour coded and closed in account/category management, while the base types remain available.

Accounts describe the money flow; categories describe its purpose. Selecting an account/type limits the category list to matching categories. Login and encryption accounts are described later under user account and restore key.

## 12. Month close

Open **Cockpit → Month-end close…**. It computes actual **income − expenses − savings**. A surplus can be booked to savings and a deficit can be covered from savings that had funds at that month-end. Only flexible budgets are mentioned as possible future reductions.

**Mark month as closed** is only a cockpit reminder flag. It does not lock budgets or transactions. Reopen the assistant after corrections to recalculate.

## 13. Favorites and search

Favorites are frequently reviewed categories and are available through the cockpit/F12 dashboard.

Use **Extras → Global Search / Ctrl+F** for transactions, budgets and categories. Enter at least two characters and double-click a result to navigate.

## 14. Export, PDF and printing

**Extras → Export / Ctrl+E** exports tracking, budget and optionally categories for one year or all years.

Available formats are CSV with an optional UTF-8 BOM, tab-separated TXT, XLSX with separate worksheets, and a print-friendly A4 PDF report. XLSX includes filters and frozen headers. An interactive print preview is not part of the export dialog.

Export is not a backup; use `.bmr` for recovery.
## 15. User account, restore key and data

Security levels are Quick, PIN and password. Account name, secret and level can be changed; sensitive operations may require reauthentication.

Store the restore key separately from backups. A person with both restore key and encrypted `.enc` database can decrypt the data.

The **Account** page or **File → Settings → Account & data** shows the effective data folder, moves data with a safety backup, opens backup/restore and database management. The new path becomes fully active after restart.

`.bmr` backups may include the database, settings and the user account that belongs to that database. If several local accounts exist, only the matching account entry is included. Automatic interval, retention and cleanup are configurable. Database management shows statistics/migrations, cleans technical leftovers and contains the only normal reset; protected accounts must reauthenticate.

Since v2.2.48 the database, settings and account metadata each have their own SHA-256 integrity check. Damaged or subsequently changed members are rejected, and confirmed legacy backups can be upgraded to a fully checked copy. These checks detect corruption but do not prove who created a backup, so restore complete account backups only from a trusted source. A Quick-account bundle may contain the local database key; treat the `.bmr` file like a password and do not place it unprotected in a public cloud folder.

Source or portable starts may use the default `data/` folder. When several program folders exist, rely on the path shown in the status bar.

## 16. Settings and appearance

**File → Settings / Ctrl+,** covers general locale/start options, workflow, tracking, learning, Soft Zero, carryover, appearance, shortcuts and account/data.

BudgetManager uses its own design profiles. Since v2.2.33 the sidebar background also comes from the app profile, so a dark GNOME theme must not override a light BudgetManager profile. A language change is fully applied after restart.

### Simple and advanced mode

Use **View → Experience mode** to switch at any time:

- **Simple:** cockpit, budget, tracking and overview; categories and savings goals remain available through dialogs or after switching mode.
- **Advanced:** shows every main tab and the complete standard cockpit.

Manually changed tabs or cockpit panels are recognised as **Custom**. No data or feature is deleted.

## 17. Important shortcuts

F1 help, Ctrl+F1 shortcut list, Ctrl+N transaction, Ctrl+F search, Ctrl+S save, Ctrl+K categories, Ctrl+T tags, Ctrl+E export, Ctrl+0…5 navigation, Ctrl+Z/Ctrl+Shift+Z undo/redo, Ctrl+Shift+F fixed/recurring, F5 refresh and F10/F11 maximise/full screen. All are editable.

## 18. Updates and diagnostics

**Extras → Updates / Ctrl+U** verifies the manifest and integrity, downloads the matching package and prepares installation while preserving the data folder.

The Help menu opens application/crash logs, diagnostics folder and creates a diagnostics ZIP. It deliberately excludes database and backups; review it before sharing.

## 19. Good routine

Daily: record transactions. Weekly: review filters and overview. Monthly: book due items, review month-end close and proposals, create a backup. Yearly: copy the year, review fixed/pot/incremental categories and enter 13th salary separately.

## Wiki audit and graphical relationships

Open **Help → Relationships and diagrams** for an offline page with three diagrams covering the full workflow, the Budget/Tracking data flow and the feedback loop through Overview, warnings and budget adjustment. The **?** at the top right of the menu bar – right next to minimise/maximise/close – opens the searchable handbook. The **? Help** button at the bottom of the sidebar does the same. Both use plain text rather than an emoji so they stay visible on Linux without an emoji font.

Since v2.2.41 empty cockpit tiles drop to the end of their column automatically. To keep your own arrangement, switch on **Pin tiles**: the order then stays put and tiles can be dragged by their header, across columns too.

Since v2.2.38 the **Help** menu is split into five groups: reference (handbook, knowledge base, visual overviews), learning (keyboard shortcuts, getting started), a **Troubleshooting** submenu (application log, crash log, diagnostics folder, diagnostic report, recovery key), version (check for updates, what's new) and finally About. The update check previously lived under Extras.
