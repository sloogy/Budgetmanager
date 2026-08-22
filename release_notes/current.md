## 2.2.72 – 22. August 2026

### LifePlanner-Integration

- Modulmanifest auf `lifeplanner.module.v2` angehoben und die kompatible Host-Reihe dauerhaft als `>=0.5.15,<0.6` hinterlegt.
- Bridge-Verträge für BudgetManager → FPM, FPM → BudgetManager und Sparziele sind deklarativ im Modulmanifest beschrieben.
- Der LifePlanner kann die Host-Kompatibilität damit nicht nur beim Installieren, sondern auch bei späteren Starts erneut prüfen.
- Der `.lpmodule`-Builder übernimmt `requires_host` aus derselben Manifestquelle, sodass Paket- und Laufzeitvertrag nicht auseinanderlaufen können.

### Release-Härtung

- Reproduzierbarer `release-trigger/vX.Y.Z`-Vorlauf ergänzt; fehlgeschlagene Vorläufe können als `release-trigger/vX.Y.Z-rN` erneut gestartet werden, ohne den eigentlichen Release-Tag zu verschieben.
- Versionsdateien werden synchronisiert, `main` wird nur per Fast-Forward übernommen und Release-Tags werden niemals überschrieben.
- Der Prepare-Lauf startet den vollständigen bestehenden Build auf exakt derselben Commit-SHA und übernimmt dessen Exit-Status.
- `release-prepare.yml` ist im strengen Lint-/Release-Prozedurcheck zugelassen, darf aber selbst keine Assets oder GitHub Releases veröffentlichen; `build.yml` bleibt der einzige Publisher.
- Der vorher rote Gate-Lauf durch die alte Workflow-Allowlist ist damit behoben, ohne den Gate zu lockern.
