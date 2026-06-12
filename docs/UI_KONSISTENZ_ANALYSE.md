# UI-Konsistenz-Analyse — Budgetmanager v0.3.7.0

> Analyse aller Kontextmenüs, Buttons, Tabellen-Konfigurationen und
> Interaktionsmuster auf Inkonsistenzen. Stand: 13.02.2026

---

## 1. Kontextmenüs (Rechtsklick) — VOR dem Fix

| View / Dialog | Kontextmenü? | Emojis? | Aktionen |
|---|---|---|---|
| **Budget-Tab** | ✅ Ja (umfangreich) | ✅ Voll | Eigenschaften, Umbenennen, Fix/Rec-Toggle, Neu, Löschen, Favoriten, Budget |
| **Tracking-Tab** | ✅ Ja (minimal) | ❌ Keine | Bearbeiten, Tags, Löschen |
| **Kategorien-Tab** | ✅ Ja | ⚠️ Teilweise | Neu, Umbenennen, Löschen, Masse, Fix/Rec/Tag (ohne Emoji) |
| **Kategorien-Manager** | ✅ Ja | ⚠️ Teilweise | Umbenennen, Unterkategorie, Fix/Rec/Tag (ohne Emoji), Löschen |
| **Budget-Entry Dialog** | ✅ Ja (⚙-Menü) | ⚠️ Teilweise | Neu, Unterkategorie, Umbenennen, Löschen, Fix/Rec/Tag (ohne Emoji) |
| **Sparziele-Dialog** | ❌ Nein | — | Nur Buttons ohne Emojis |
| **Tags-Manager** | ❌ Nein | — | Nur Buttons (mit Emojis) |
| **Wiederkehrende Trans.** | ❌ Nein | — | Nur Buttons (mit Emojis) |
| **Favoriten-Dashboard** | ❌ Nein | — | Nur Anzeige |
| **Übersicht-Tab** | ❌ Nein | — | Mehrere Tabellen ohne Kontextmenüs |

### Fazit VOR Fix
- 4/10 Views hatten ein Kontextmenü
- Emoji-Verwendung war inkonsistent (✓/☐ vs. keine vs. volle Emojis)
- 3 Dialoge mit Tabellen hatten weder Kontextmenü noch Doppelklick

---

## 2. Durchgeführte Fixes (v0.3.7.0)

### Einheitliches Emoji-Schema
| Emoji | Verwendung | Konsistent in |
|---|---|---|
| ✏️ | Bearbeiten / Umbenennen | Alle Menüs + Buttons |
| 🗑️ | Löschen | Alle Menüs + Buttons |
| ➕ | Neu erstellen | Alle Menüs + Buttons |
| 📂 | Unterkategorie / Ordner | Budget, Kategorien, Manager |
| ⚙️ | Eigenschaften | Budget-Tab |
| 📌 | Fixkosten Toggle | Budget, Kategorien, Manager, Entry-Dialog |
| 🔁 | Wiederkehrend Toggle | Budget, Kategorien, Manager, Entry-Dialog |
| 📅 | Fälligkeitstag | Budget, Kategorien, Manager, Entry-Dialog |
| 🏷️ | Tags | Tracking-Tab |
| 📋 | Duplizieren | Tracking-Tab |
| 💰 | Budget-Aktionen | Budget-Tab |
| ⭐/☆ | Favoriten | Budget-Tab |
| 📈 | Fortschritt | Sparziele |
| 🎨 | Farbe ändern | Tags-Manager |
| ⏸️ | Aktivieren/Deaktivieren | Wiederkehrende Trans. |

### Fix-Details
1. **Tracking-Tab:** Emojis ergänzt, „Duplizieren"-Aktion hinzugefügt
2. **Budget-Tab:** ✓/☐ → 📌/🔁, `...` → `…`, fehlendes 💰 vor „Budget bearbeiten"
3. **Kategorien-Tab:** 📌/🔁/📅 bei Toggle-Aktionen ergänzt
4. **Kategorien-Manager:** 📌/🔁 bei Toggle-Aktionen ergänzt
5. **Budget-Entry Dialog:** 📌/🔁/📅 bei Menü-Aktionen ergänzt
6. **Sparziele-Dialog:** Emojis an Buttons + Kontextmenü + Doppelklick
7. **Tags-Manager:** alternatingRowColors + verticalHeader + Kontextmenü + Doppelklick
8. **Wiederkehrende Trans.:** verticalHeader + Kontextmenü

---

## 3. Tabellen-Konfiguration — Überblick

| View / Dialog | SelectRows | NoEditTriggers | AltRowColors | VertHeader hidden | Kontextmenü | Doppelklick |
|---|---|---|---|---|---|---|
| Budget-Tab | SelectItems¹ | Editable¹ | ✅ | — | ✅ | ✅ |
| Tracking-Tab | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| Kategorien-Tab | Extended² | Partial² | ✅ | — | ✅ | — |
| Übersicht: Budget-Tabelle | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Übersicht: Transaktionen | ✅ | ✅ | ✅ | ✅ | — | — |
| Übersicht: Sparziele | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Übersicht: Kategorien-Tree | ✅ | — | ✅ | — | — | ✅ |
| Sparziele-Dialog | ✅ | ✅ | ✅ | ✅ ⬆️ | ✅ ⬆️ | ✅ ⬆️ |
| Tags-Manager | ✅ | — | ✅ ⬆️ | ✅ ⬆️ | ✅ ⬆️ | ✅ ⬆️ |
| Wiederkehrende Trans. | ✅ | — | ✅ | ✅ ⬆️ | ✅ ⬆️ | ✅ |
| Favoriten-Dashboard | ✅ | ✅ | ✅ | — | — | — |
| Globale Suche | ✅ | ✅ | ✅ | — | — | — |

¹ Budget-Tab erlaubt direkte Zellbearbeitung (gewollt)
² Kategorien-Tab erlaubt Mehrfachauswahl + Inline-Editing (gewollt)
⬆️ = Neu hinzugefügt in v0.3.7.0

---

## 4. Offene Punkte (Zukunft)

- **Übersicht-Tab:** Transaktions-Tabelle könnte ein Kontextmenü bekommen
  (z.B. „Zum Tracking-Tab springen", „Kategorie filtern")
- **Favoriten-Dashboard:** Kontextmenü möglich (z.B. „Von Favoriten entfernen")
- **Globale Suche:** Kontextmenü für Navigation (TODO bereits vorhanden im Code)
- **verticalHeader:** Könnte in Tracking-Tab und einigen Dialogen
  auch ausgeblendet werden (minimaler visueller Effekt)
- **Ellipsis:** Einige weitere Dialoge verwenden noch `...` statt `…`
