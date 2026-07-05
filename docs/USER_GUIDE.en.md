# BudgetManager 2.2.6 – User guide

## 1. Core idea

BudgetManager runs locally on your computer. The app stores budgets, transactions, categories, backups and settings in the data folder. In the portable version this folder is next to the app as `data/`.

Recommended workflow:

1. Check or create categories.
2. Enter the monthly budget.
3. Record real transactions in Tracking.
4. Review the Overview and charts.
5. Create a backup before major changes.

## 2. Categories

Categories always belong to one type: income, expenses or savings. Subcategories can only be moved within the same type. Drag & drop lets you move a category below a parent or back to the top level.

Flags:

- **Fixed cost**: planned cost or reserve, for example rent, insurance, deductible or medical reserve.
- **Recurring**: regularly recurring transaction.
- **Fixed + recurring**: true monthly fixed cost. The monthly budget amount is used when booking.
- **Fixed without recurring**: protected variable reserve. The booking amount can be changed.
- **Recurring without fixed**: regular but variable transaction. The booking amount can be changed.

## 3. Budget

In the Budget tab you enter the planned amount per category and month. A budget does not create a transaction. It is only the plan.

Important rules:

- Empty cells are 0.
- Parent categories show child totals plus their own buffer.
- The total row shows the sum of the visible area.
- A year can be copied from an existing year, with or without amounts.

## 4. Tracking / transactions

Tracking records real money movements. The category picker only shows categories of the selected type. Favorites and frequently used manual categories appear near the top; automatic fixed-cost bookings do not distort that order. Parent categories with children are not shown as bookable rows there; child categories use short labels, e.g. **Rent** instead of **Housing › Rent**.

The **Book fixed/recurring** button consciously creates the due fixed and recurring bookings for the selected month. Nothing is booked secretly in the background.

## 5. Forecast / budget suggestions

Budget suggestions are recommendations, not automatic changes. The app only checks completed months and avoids suggestions based on single outliers.

Logic:

- A single zero month is never enough to lower a budget.
- For fixed and recurring categories, zero months are ignored for reductions.
- Fixed costs need repeated real bookings before a suggestion appears.
- Flexible categories can learn from repeated patterns, even if some months contain zero.
- Opposite outliers, for example 450 CHF and then 350 CHF with a 400 CHF budget, do not trigger a suggestion.

## 6. Overview and charts

The Overview compares planned and actual values.

Chart guide:

- **Plan/actual donut**: outer ring income, middle ring expenses, inner ring savings. Each ring shows booked, still open, or over budget. This is the main monthly check.
- **Category ranking**: shows the largest expense categories as bars. This is easier to read than a large pie chart.
- **Account comparison**: shows income, expenses, and savings as bars. This replaces the confusing neighboring pie because these values are not shares of the same pot.
- **Monthly trend**: shows development over months. Useful for trends.
- **Monthly balance**: shows income minus expenses minus savings per month.
- **Top bookings**: aggregates categories and sorts by amount, so repeated salary or rent bookings do not appear as confusing duplicate rows.

If no data exists, the app shows a message instead of an empty chart.

## 7. Updates

Use **Extras → Updates…** to check for new releases. The update window shows each step.

Update paths:

- **Portable Windows/Linux**: downloads the portable ZIP, replaces program files and keeps `data/` and `updates/`.
- **Direct Windows EXE/Linux binary**: migrates old versioned launch files to stable names.
- **Windows installer**: downloads the new setup EXE, waits until the app is closed and runs the installer in update mode. The selected data folder is preserved.

## 8. Backup and restore key

The restore key is important for encrypted databases and recovery. Store it outside the BudgetManager folder, for example in Bitwarden.

Before major changes, create a backup. The data folder and `data/backups/` are not overwritten by updates.

## 5.1 Tracking learning mode

Tracking learning mode helps when no budget has been set yet. It only uses manual tracking entries and creates a suggested starting budget.

During first setup, an active learning mode lets you continue without entering a budget value. This is intentional: you can track first and let budgets be learned later from real data. If learning mode is disabled, first setup still requires at least one budget value.

The learning mode and the normal budget suggestion logic are separate:

- No budget in the selected year: learning mode may suggest a starting budget.
- Budget exists in the selected year: learning mode ends and the normal suggestion logic takes over.
- A suggestion never changes data automatically.
- When applying it, you confirm the budget kind first.

Right-click a learned suggestion in the suggestion dialog to keep observing, ignore it, mark it as irregular/reserve, or reset its learning status. This is useful for health costs, deductibles, repairs, and other irregular expenses.

In the overview banner, new learned starting budgets use **🆕**. Real deficit/increase warnings still use **📉**, while surplus/decrease suggestions use **📈**.

## 5.2 Year-end copy with learning mode

When copying a year, BudgetManager also checks categories that were tracked but never budgeted in the source year. They appear as possible starting budgets for the new year and can be accepted or deselected.
