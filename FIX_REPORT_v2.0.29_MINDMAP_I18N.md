# BudgetManager v2.0.29 – Mindmap i18n Fix

## Ziel

Die direkt anzeigbare Mindmap war nur auf Deutsch vorhanden. Sie sollte analog zur App-Hilfe auch auf Englisch und Französisch verfügbar sein.

## Umsetzung

### 1. Sprachvarianten ergänzt

Neue lokale HTML-Dateien:

- `docs/help/mindmap.de.html`
- `docs/help/mindmap.en.html`
- `docs/help/mindmap.fr.html`

Neue Mermaid-Quellen:

- `docs/help/mindmap.de.mmd`
- `docs/help/mindmap.en.mmd`
- `docs/help/mindmap.fr.mmd`

Die bisherigen Dateien bleiben aus Kompatibilitätsgründen erhalten:

- `docs/help/mindmap.html` = deutsche Fallback-Datei mit Sprachlinks
- `docs/help/mindmap.mmd` = deutsche Fallback-Mermaid-Datei

### 2. App-Integration angepasst

`views/main_window.py` öffnet bei **Hilfe → Informations-Laufplan / Mindmap anzeigen…** nun die sprach passende Datei:

- App-Sprache Deutsch → `docs/help/mindmap.de.html`
- App-Sprache Englisch → `docs/help/mindmap.en.html`
- App-Sprache Französisch → `docs/help/mindmap.fr.html`
- unbekannte Sprache / fehlende Datei → Fallback `docs/help/mindmap.html`

### 3. Dokumentation aktualisiert

Aktualisiert wurden:

- `README.md`
- `README_INSTALLATION.md`
- `docs/help/README.md`
- `docs/help/index.html`

### 4. Regressionstest ergänzt

`tests/test_workflow_defaults.py` prüft jetzt:

- alle drei HTML-Mindmaps existieren,
- alle drei Mermaid-Quellen existieren,
- EN/FR enthalten nicht versehentlich die wichtigsten deutschen Mindmap-Begriffe.

## Validierung

```text
compileall: PASS
i18n audit: PASS
100-Loop Release-Logiktest: PASS
pytest: 158 passed, 2 skipped
```

## Bewertung

Der gemeldete Punkt ist behoben. Die Mindmap ist jetzt für Deutsch, Englisch und Französisch verfügbar und der App-Menüpunkt öffnet sprachabhängig die passende Variante.
