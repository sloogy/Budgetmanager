# Release-Verifikation v2.2.36 – Wiki-Audit und Linux-Hilfe

## Behobener Linux-Fehler

In der linken Seitenleiste fehlte auf Linux/Fedora der erwartete Hilfe-Einstieg mit Fragezeichen. Der neue Knopf verwendet bewusst normalen ASCII-Text:

```text
? Hilfe
```

Dadurch ist er nicht von einer Emoji-Schrift oder vom GNOME-Icon-Theme abhängig. Ein Klick öffnet das durchsuchbare In-App-Handbuch.

## Wiki-Integration

- Neuer Menüpunkt **Hilfe → Wiki-Audit & Zusammenhänge**.
- Neuer Knopf **Wiki-Grafiken anzeigen** im In-App-Handbuch.
- Neues dreisprachiges Handbuchthema **Wiki-Audit & Zusammenhänge**.
- Responsive Offline-Seite `docs/help/wiki-audit.html`.
- Drei integrierte Grafiken unter `docs/help/assets/`:
  - `wiki_audit_overview.png`
  - `dataflow_decision_logic.png`
  - `wiki_audit_dashboard.png`
- PyInstaller nimmt den gesamten Ordner `docs/help` mit; die Grafiken sind damit auch im Linux- und Windows-Build enthalten.

## Prüfungen

- Python-Kompilierung: bestanden.
- Wiki-/Handbuch-Audit: 10/10 Prüfbereiche bestanden.
- i18n-Audit DE/EN/FR: bestanden.
- Versionssynchronisierung: bestanden.
- Release-Logik-Audit: 100 Durchläufe, 0 Findings.
- Final-Release-Audit: 1.000 Durchläufe, 19.005 Prüfungen, 0 Warnungen, 0 Fehler.
- Architektur-Gate: bestanden.
- Lint-/Release-Prozedur: bestanden.
- Tests in drei vollständigen Batches:
  - 634 bestanden,
  - 9 übersprungen,
  - 2 umgebungsbedingt nicht ausführbar: `bandit` und `PySide6` fehlen im Prüfcontainer.

## Manueller Sichttest

Auf Fedora/GNOME prüfen:

1. BudgetManager starten.
2. Links unten muss **? Hilfe** über **Einstellungen** sichtbar sein.
3. Auf **? Hilfe** klicken – das In-App-Handbuch muss öffnen.
4. Unten **Wiki-Grafiken anzeigen** anklicken.
5. Die lokale Seite mit allen drei Grafiken muss im Standardbrowser erscheinen.
