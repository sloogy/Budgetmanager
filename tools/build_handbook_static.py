#!/usr/bin/env python3
"""Build the static German handbook from the canonical user guide.

The in-app help stays topic based. The browser-readable handbook is generated
from ``docs/USER_GUIDE.de.md`` so corrections are not copied manually into two
separate long files.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _preamble(version: str) -> str:
    return f"""# BudgetManager Hilfe {version}

## Vereinheitlichte Bedienung

Die **linke Seitenleiste** ist die Hauptnavigation. Neue Buchungen aus Cockpit, Tracking und Aktionsleiste öffnen **denselben vollständigen Buchungsdialog**. Budget ist der Plan, Tracking enthält die echten Buchungen.

| System | Zweck |
|---|---|
| Budget | Sollbetrag pro Kategorie und Monat |
| Tracking | Tatsächliche Einnahmen, Ausgaben und Ersparnisse |
| POT/Rückstellung | Reserviertes Budget für erwartete unregelmässige Kosten |
| Sparziel | Fester Zielbetrag mit Einzahlungen und Entnahmen |
| `.bmr` | Wiederherstellbares BudgetManager-Backup |
| CSV/TXT | Export für Auswertung, nicht für Restore |

> Direkt anzeigbare Mindmap: `docs/help/mindmap.de.html`. Die In-App-Hilfe ist mit **F1** durchsuchbar.

---

"""


def _mindmap_footer() -> str:
    return """

## Informations-Laufplan / Mindmap

Der empfohlene Ablauf ist:

```text
Erststart → Konto und Restore-Key → Kategorien → Budget oder Lernmodus
→ Buchungen → Übersicht → Monatsabschluss → Backup
```

Die Browser-Versionen liegen unter:

- `mindmap.de.html`
- `mindmap.en.html`
- `mindmap.fr.html`

`mindmap.html` bleibt die deutsche Fallback-Datei.

## Wiki-Audit und grafische Zusammenhänge

Die vollständige Offline-Grafikseite ist hier verfügbar:

- [Wiki-Audit & Zusammenhänge öffnen](wiki-audit.html)

Der sichtbare **? Hilfe**-Knopf der Linux-Seitenleiste verwendet bewusst normalen Text statt eines Emoji-Glyphen.
"""


def _html_document(markdown_text: str, version: str) -> str:
    try:
        import mistune
    except ImportError as exc:  # pragma: no cover - build environment guard
        raise SystemExit(
            "mistune fehlt. Installiere die Entwicklungsabhängigkeiten, bevor "
            "die statische Hilfe gebaut wird."
        ) from exc

    renderer = mistune.create_markdown(plugins=["table"])
    body = renderer(markdown_text)
    css = """
:root{color-scheme:light dark}body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.58;max-width:1120px;margin:32px auto;padding:0 24px;color:#18202a;background:#fff}h1,h2,h3,h4{color:#0b7285;line-height:1.25;margin-top:1.7em}h1{border-bottom:2px solid #0b7285;padding-bottom:.35rem}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #cbd3da;padding:.55rem .7rem;text-align:left;vertical-align:top}th{background:#eef6f7}pre{background:#f3f5f7;padding:14px;border-radius:7px;overflow:auto}code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}blockquote{border-left:4px solid #0b7285;margin:1rem 0;padding:.45rem 1rem;background:#f5fafb}a{color:#0b7285}hr{border:0;border-top:1px solid #d9e0e5;margin:2rem 0}@media(prefers-color-scheme:dark){body{color:#e8edf2;background:#15191d}h1,h2,h3,h4,a{color:#67c7d2}th{background:#263238}th,td{border-color:#48545d}pre,blockquote{background:#20272c}}
""".strip()
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>BudgetManager Hilfe {version}</title><style>{css}</style></head>"
        f"<body>{body}</body></html>\n"
    )


def main() -> int:
    from app_info import APP_VERSION

    guide = (ROOT / "docs/USER_GUIDE.de.md").read_text(encoding="utf-8").strip()
    markdown_text = _preamble(APP_VERSION) + guide + _mindmap_footer()
    readme = ROOT / "docs/help/README.md"
    html = ROOT / "docs/help/index.html"
    readme.write_text(markdown_text.rstrip() + "\n", encoding="utf-8")
    html.write_text(_html_document(markdown_text, APP_VERSION), encoding="utf-8")
    print(f"Built {readme.relative_to(ROOT)} and {html.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
