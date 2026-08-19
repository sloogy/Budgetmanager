# Coverage-Nachweis

Die Datei `coverage.json` aus v2.2.49 war eine lokale Teilmessung und wurde
entfernt, damit sie nicht mit der vollständigen CI-Abdeckung verwechselt wird.

Die CI erzeugt ab v2.2.51 eindeutig benannte Artefakte:

- `coverage_full.json` – vollständige Test-Suite mit PySide6
- `coverage_full.xml` – Importformat für CI-Dienste
- `coverage_gate_summary.json` – Gesamtgrenze und Einzelgrenzen der kritischen Module

Ein Release ist nur zulässig, wenn `coverage_gate_summary.json` sowohl
`overall.passed=true` als auch `passed=true` ausweist.
