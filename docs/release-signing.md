# Release-Signierung und Vertrauenskette

## Einmalige GitHub-Konfiguration

Der Tag-Build ist absichtlich fail-closed. Ohne diese Werte wird kein Release erzeugt:

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
