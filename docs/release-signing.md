# Release-Signierung und Vertrauenskette

## Aktueller Release-Modus

Alle per `v*`-Tag erzeugten Windows-/Linux-Builds muessen einen eingebetteten
Update-Vertrauensanker enthalten. Fehlt `UPDATE_SIGNING_PUBLIC_KEY_B64`, bricht
der Build absichtlich ab. Auch `latest.json.sig` ist fuer den Release zwingend.
Damit wird verhindert, dass erneut eine Version ausgeliefert wird, die spaeter
keine sicheren automatischen Updates verifizieren kann.

BudgetManager v2.2.61 kann den Vertrauensanker bereits aus
``_internal/resources/update_signing_public_key.b64`` lesen. Fuer diese Version
wird deshalb im Release ein einmaliger ``BudgetManager-v2.2.61-Trust-Bridge.ps1``
mitgeliefert. Er schreibt ausschliesslich den oeffentlichen Key in diesen bereits
unterstuetzten Pfad und startet danach den normalen signaturpruefenden Updater.
Die Signaturpruefung wird zu keinem Zeitpunkt abgeschaltet und es ist keine
Neuinstallation notwendig.

## Einmalige GitHub-Konfiguration für den finalen Release

Vor dem finalen Release müssen diese Werte eingerichtet und das Signatur-Gate
wieder verpflichtend aktiviert werden:

- Repository Variable `UPDATE_SIGNING_PUBLIC_KEY_B64`
- Repository Secret `UPDATE_SIGNING_PRIVATE_KEY_B64`
- Repository Secret `WINDOWS_CODESIGN_PFX_B64`
- Repository Secret `WINDOWS_CODESIGN_PASSWORD`

Das Ed25519-Schlüsselpaar wird lokal mit `python tools/generate_update_signing_key.py` erzeugt. Der private Schlüssel darf weder committed noch als Artefakt hochgeladen werden. Der öffentliche Schlüssel wird beim Build in die Anwendung eingebettet.

Das Windows-PFX muss ein gültiges Code-Signing-Zertifikat mit privatem Schlüssel enthalten. Der Workflow signiert und verifiziert sowohl `BudgetManager.exe` als auch den Installer mit SHA-256 und vertrauenswürdigem Zeitstempel.

## Automatische Nachweise

Jeder Release enthält:

- `latest.json` und `latest.json.sig`
- `SHA256SUMS.txt`
- CycloneDX-SBOM `BudgetManager-v<Version>.cdx.json`
- GitHub Build-Provenance/Attestation für alle Release-Artefakte
- Authenticode-signierte Windows-Binaries

Die Anwendung lädt Updates nur per HTTPS und verwirft fehlende oder ungültige Ed25519-Signaturen.
