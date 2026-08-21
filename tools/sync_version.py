#!/usr/bin/env python3
"""Synchronisiert die Versionsnummer aus app_info.py in Release-Dateien.

Einzige manuelle Versionsquelle: app_info.py (APP_VERSION, APP_RELEASE_DATE)

Aktualisiert/prueft:
    - version.json
    - VERSION_INFO.txt (Kopfzeile + Datum)
    - installer/budgetmanager_setup.iss (#define MyAppVersion)
    - latest.json.template
    - docs/latest.json.template

Aufruf aus dem Projekt-Root:
    python tools/sync_version.py
    python tools/sync_version.py --check
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_info import APP_NAME, APP_VERSION, APP_RELEASE_DATE  # noqa: E402


def _latest_template_data() -> dict:
    tag = f"v{APP_VERSION}"
    base = f"https://github.com/sloogy/Budgetmanager/releases/download/{tag}"
    return {
        "app": APP_NAME,
        "channel": "stable",
        "version": APP_VERSION,
        "release_tag": tag,
        "assets": {
            "windows": {
                "type": "portable-zip",
                "url": f"{base}/BudgetManager-v{APP_VERSION}-portable-windows.zip",
                "sha256": "PUT_SHA256_HERE",
            },
            "linux": {
                "type": "portable-zip",
                "url": f"{base}/BudgetManager-v{APP_VERSION}-portable-linux.zip",
                "sha256": "PUT_SHA256_HERE",
            },
            "portable_windows_zip": {
                "type": "portable-zip",
                "url": f"{base}/BudgetManager-v{APP_VERSION}-portable-windows.zip",
                "sha256": "PUT_SHA256_HERE",
            },
            "portable_linux_zip": {
                "type": "portable-zip",
                "url": f"{base}/BudgetManager-v{APP_VERSION}-portable-linux.zip",
                "sha256": "PUT_SHA256_HERE",
            },
            "portable_zip": {
                "type": "portable-zip",
                "url": f"{base}/BudgetManager-v{APP_VERSION}-portable-windows.zip",
                "sha256": "PUT_SHA256_HERE",
            },
            "windows_installer": {
                "type": "installer",
                "url": f"{base}/BudgetManager_Setup_{APP_VERSION}.exe",
                "sha256": "PUT_SHA256_HERE",
            },
            "windows_installer_zip": {
                "type": "installer-zip",
                "url": f"{base}/BudgetManager_Setup_{APP_VERSION}.zip",
                "sha256": "PUT_SHA256_HERE",
            },
        },
    }


def sync_version_json(check: bool) -> bool:
    p = ROOT / "version.json"
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    ok = data.get("version") == APP_VERSION and data.get("app") == APP_NAME
    if check or ok:
        return ok
    data["app"] = APP_NAME
    data["version"] = APP_VERSION
    p.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


def sync_version_info_txt(check: bool) -> bool:
    p = ROOT / "VERSION_INFO.txt"
    if not p.exists():
        return True
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return True
    expected_head = f"{APP_NAME} Version {APP_VERSION}\n"
    ok = lines[0].rstrip("\n") == expected_head.rstrip("\n")
    date_ok = any(line.strip() == f"Datum: {APP_RELEASE_DATE}" for line in lines[:10])
    if check:
        return ok and date_ok
    if not ok:
        lines[0] = expected_head
    if not date_ok:
        for i, line in enumerate(lines[:10]):
            if line.startswith("Datum:"):
                lines[i] = f"Datum: {APP_RELEASE_DATE}\n"
                break
    p.write_text("".join(lines), encoding="utf-8")
    return True


def sync_installer(check: bool) -> bool:
    p = ROOT / "installer" / "budgetmanager_setup.iss"
    if not p.exists():
        return True
    src = p.read_text(encoding="utf-8")
    new = re.sub(
        r'#define MyAppVersion "[^"]*"',
        f'#define MyAppVersion "{APP_VERSION}"',
        src,
    )
    ok = new == src
    if check or ok:
        return ok
    p.write_text(new, encoding="utf-8")
    return True


def sync_latest_template(rel_path: str, check: bool) -> bool:
    p = ROOT / rel_path
    expected = _latest_template_data()
    try:
        current = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        current = {}
    ok = current == expected
    if check or ok:
        return ok
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


def _swap_version(text: str, old_series: str) -> str:
    """Ersetzt Versionen der laufenden Reihe, laesst aeltere als Verlauf stehen.

    Weder Wortgrenze noch Punktverbot am Rand: die Version steht auch als
    "v2.2.63" mitten im Wort und als "_2.2.63.exe" vor einer Endung. Der Blick
    nach vorn wehrt nur laengere Versionen ab.
    """
    return re.sub(rf"(?<![\d.]){re.escape(old_series)}\.\d+(?!\.?\d)", APP_VERSION, text)


# Dateien, die die Version in ihrem Kopf nennen, mit der Anzahl Zeilen, die
# dazu gehoert. Weiter unten steht in denselben Dateien die Versionshistorie
# ("Neu in v2.2.41") - die darf nicht mitwandern. Die Release-Gates in
# tests/test_release_integrity.py pruefen genau diese Liste; bisher musste sie
# bei jedem Release von Hand nachgezogen werden.
VERSION_BEARING: tuple[tuple[str, int], ...] = (
    ("README.md", 5),
    ("README_INSTALLATION.md", 5),
    ("updater/README.md", 5),
    ("updater/generate_manifest.py", 12),
    ("docs/architecture.md", 5),
    ("docs/DAU_TEST_ERSTSTART.md", 5),
    ("docs/features.md", 5),
    ("docs/migration-guide.md", 5),
    ("docs/open-tasks.md", 5),
    ("docs/package-overview.md", 5),
    ("docs/release-checklist.md", 5),
    ("docs/themes.md", 5),
    ("docs/USER_GUIDE.de.md", 5),
    ("docs/USER_GUIDE.en.md", 5),
    ("docs/USER_GUIDE.fr.md", 5),
)

# In README.md steht die Version zusaetzlich als Codebeispiel.
EXTRA_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("README.md", r'APP_VERSION = "[^"]*"', 'APP_VERSION = "{version}"'),
)

_VERSION_IN_SERIES = r"(?<![\d.]){series}\.\d+(?!\.?\d)"


def _head_version(lines: list[str], series: str) -> str | None:
    """Die Version, die der Kopf der Datei als die aktuelle fuehrt."""
    pattern = re.compile(_VERSION_IN_SERIES.format(series=re.escape(series)))
    for line in lines:
        found = pattern.search(line)
        if found:
            return found.group(0)
    return None


def sync_markdown_headings(check: bool) -> bool:
    """Zieht die Version im Kopf jeder Datei nach - und nur dort.

    ``docs/help/README.md`` und ``docs/help/index.html`` entstehen aus diesen
    Quellen; ``tools/build_handbook_static.py`` baut sie neu.
    """
    series = APP_VERSION.rsplit(".", 1)[0]
    ok = True
    for rel, head_lines in VERSION_BEARING:
        p = ROOT / rel
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        lines = src.splitlines(keepends=True)
        previous = _head_version(lines[:head_lines], series)
        new = src
        if previous and previous != APP_VERSION:
            head = "".join(lines[:head_lines]).replace(previous, APP_VERSION)
            new = head + "".join(lines[head_lines:])
        for target, pattern, replacement in EXTRA_PATTERNS:
            if target == rel:
                new = re.sub(pattern, replacement.format(version=APP_VERSION), new)
        if new == src:
            continue
        if check:
            ok = False
            continue
        p.write_text(new, encoding="utf-8")
    return ok


def sync_features(check: bool) -> bool:
    """FEATURES.md sammelt je Release einen Abschnitt "Neu in vX".

    Hier wird nichts umbenannt - ein fehlender Abschnitt wird vorangestellt,
    damit die Liste der vorigen Releases erhalten bleibt.
    """
    p = ROOT / "FEATURES.md"
    if not p.exists():
        return True
    src = p.read_text(encoding="utf-8")
    heading = f"## Neu in v{APP_VERSION}"
    if heading in src:
        return True
    if check:
        return False
    p.write_text(f"{heading}\n\n- Siehe VERSION_INFO.txt und CHANGELOG.md.\n\n{src}",
                 encoding="utf-8")
    return True


def sync_release_notes(check: bool) -> bool:
    """VERSION_INFO.txt beginnt mit den Notizen der aktuellen Version.

    Der erste Block traegt einen Titel in Grossbuchstaben mit Trennlinie und
    nennt die Version. Steht dort noch die vorige, wird ihre Nummer im Titel
    nachgezogen - der Text bleibt, er beschreibt ja dieselbe Auslieferung.
    """
    p = ROOT / "VERSION_INFO.txt"
    if not p.exists():
        return True
    src = p.read_text(encoding="utf-8")
    head = f"Budgetmanager Version {APP_VERSION}\nDatum: {APP_RELEASE_DATE}\n"
    parts = src.split("\n\n", 2)
    if len(parts) < 2:
        return True
    body = parts[1]
    title = body.splitlines()[0] if body.splitlines() else ""
    if APP_VERSION not in title:
        series = APP_VERSION.rsplit(".", 1)[0]
        fixed = _swap_version(title, series)
        if APP_VERSION not in fixed:
            fixed = f"{title.rstrip()} {APP_VERSION}"
        body = "\n".join([fixed] + body.splitlines()[1:])
    new = head + "\n" + body + ("\n\n" + parts[2] if len(parts) > 2 else "\n")
    ok = new == src
    if check or ok:
        return ok
    p.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    check = "--check" in sys.argv
    results = {
        "version.json": sync_version_json(check),
        "VERSION_INFO.txt": sync_version_info_txt(check),
        "installer/budgetmanager_setup.iss": sync_installer(check),
        "latest.json.template": sync_latest_template("latest.json.template", check),
        "docs/latest.json.template": sync_latest_template(
            "docs/latest.json.template", check
        ),
        "Versionskoepfe in Doku und Updater": sync_markdown_headings(check),
        "FEATURES.md": sync_features(check),
        "VERSION_INFO.txt (Release-Notizen)": sync_release_notes(check),
    }
    if check:
        bad = [name for name, ok in results.items() if not ok]
        if bad:
            print(f"VERSION MISMATCH (Quelle app_info.py = {APP_VERSION}):")
            for name in bad:
                print(f"  - {name} ist nicht synchron")
            return 1
        print(f"Alle Versionsdateien synchron: {APP_VERSION}")
        return 0
    print(f"Versionen synchronisiert auf {APP_VERSION} ({APP_RELEASE_DATE})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
