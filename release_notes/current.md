## 2.2.67 – 21. August 2026

### Hotfix: Theme-Editor und Update-Diagnose

- Der Theme-Editor verwendet die Schliessen-Leiste jetzt im korrekten Layout-Scope; der `NameError: name 'outer' is not defined` ist behoben und regression-getestet.
- Signatur-/Vertrauensfehler des Updaters werden nicht mehr faelschlich als Netzwerk-/Manifestfehler ausgegeben.

### Einmaliger Trust Bridge fuer v2.2.61 – keine Neuinstallation

BudgetManager v2.2.61 unterstuetzt bereits einen externen Update-Public-Key unter `_internal/resources/update_signing_public_key.b64`. Der Release erzeugt deshalb `BudgetManager-v2.2.61-Trust-Bridge.ps1`. Das Skript hinterlegt ausschliesslich den oeffentlichen Ed25519-Vertrauensanker in der bestehenden Installation und startet danach den unveraenderten signaturpruefenden Updater.

Ein vorhandener abweichender Key wird nicht ueberschrieben. Der private Signierschluessel ist niemals Bestandteil des Bridge-Skripts. Damit kann eine installierte 2.2.61 direkt auf 2.2.67 aktualisiert werden, ohne Neuinstallation und ohne die Signaturpruefung auch nur temporaer abzuschalten.
