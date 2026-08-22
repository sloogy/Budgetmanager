"""Regressionstests v2.2.39 – Funde des DAU-Enterprise-Audits.

Das Audit (``tools/dau_enterprise_audit.py``) prüft Menükonventionen,
i18n-Parität, Verweise, Signalverdrahtung, Theme-Disziplin und Erreichbarkeit.
Diese Tests halten die daraus behobenen Punkte fest.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("de", "en", "fr")
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
THEMED_DIALOGS = ("views/login_dialog.py", "views/account_management_dialog.py")


def _label(lang: str, key: str) -> str:
    data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
    return data.get(key) or data["menu"][key.split(".", 1)[1]]


def test_audit_tool_reports_no_findings():
    result = subprocess.run(
        [sys.executable, "tools/dau_enterprise_audit.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "findings=0" in result.stdout


def test_audit_source_scan_ignores_virtual_environments(monkeypatch, tmp_path):
    """Fremde Paketquellen und Jinja-Templates sind kein Projektcode."""
    module_path = ROOT / "tools/dau_enterprise_audit.py"
    spec = importlib.util.spec_from_file_location("dau_enterprise_audit", module_path)
    assert spec is not None and spec.loader is not None
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    project_file = tmp_path / "model" / "valid.py"
    project_file.parent.mkdir()
    project_file.write_text("VALUE = 1\n", encoding="utf-8")
    template = tmp_path / ".venv" / "site-packages" / "template.py"
    template.parent.mkdir(parents=True)
    template.write_text("{% if feature %}\n", encoding="utf-8")

    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit._python_files() == [project_file]


def test_login_and_account_dialogs_have_no_hardcoded_colors():
    """Bugklasse v2.2.33: Festfarben übersteuern das aktive Farbprofil."""
    for rel in THEMED_DIALOGS:
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert not HEX.search(source), f"{rel}: {HEX.findall(source)[:3]}"
        assert re.search(
            r"\bthemed\(\s*self\s*,", source
        ), f"{rel}: nutzt themed() nicht"


def test_themed_helper_uses_percent_formatting():
    """QSS besteht aus geschweiften Klammern – f-String/format scheiden aus."""
    source = (ROOT / "views/ui_colors.py").read_text(encoding="utf-8")
    block = source.split("def themed(", 1)[1]
    assert "template % values" in block
    assert "except (KeyError, ValueError, TypeError)" in block


def test_hover_colors_are_derived_from_profile():
    source = (ROOT / "views/ui_colors.py").read_text(encoding="utf-8")
    assert "from utils.color_shade import shade" in source
    for name in ("accent_hover", "positive_hover", "warning_hover", "negative_hover"):
        assert f"{name}: str = field(init=False)" in source
        assert f'object.__setattr__(self, "{name}", shade(' in source


def test_shade_is_robust_and_monotonic():
    """Farbarithmetik liegt Qt-frei in utils/color_shade.py und ist direkt testbar."""
    sys.path.insert(0, str(ROOT))
    from utils.color_shade import shade

    assert shade("#2f80ed", 0.82) != "#2f80ed"
    assert shade("#000000", 0.5) == "#000000"
    assert shade("#ffffff", 2.0) == "#ffffff"
    assert shade("nonsense", 0.8) == "nonsense"
    assert shade("", 0.8) == ""
    assert shade("#808080", 0.5) == "#404040"


def test_account_management_label_uses_single_ellipsis():
    for lang in LANGS:
        label = _label(lang, "menu.account_manage")
        assert label.endswith("…"), f"{lang}: {label!r}"
        assert "..." not in label


def test_french_menu_entries_have_access_keys():
    for key in ("menu.account_data", "menu.fullscreen"):
        assert "&" in _label("fr", key), key


def test_audit_covers_all_six_blocks():
    source = (ROOT / "tools/dau_enterprise_audit.py").read_text(encoding="utf-8")
    for block in (
        "audit_menu_conventions",
        "audit_i18n_parity",
        "audit_link_integrity",
        "audit_signal_wiring",
        "audit_theme_discipline",
        "audit_reachability",
    ):
        assert f"def {block}(" in source


def test_placeholder_check_is_limited_to_format_keys():
    """Reine Beschriftungen dürfen Platzhalternamen sprachspezifisch nennen."""
    source = (ROOT / "tools/dau_enterprise_audit.py").read_text(encoding="utf-8")
    assert "def _format_keys(" in source
    assert "key not in format_keys" in source
    model = (ROOT / "model/tags_model.py").read_text(encoding="utf-8")
    assert "{date}" in model and "{datum}" in model, "beide Schreibweisen erwartet"


def test_dau_audit_loops_do_not_repeat_static_filesystem_scan():
    """Viele Loops bestätigen dieselbe statische Invariante ohne Zeitexplosion."""
    source = (ROOT / "tools/dau_enterprise_audit.py").read_text(encoding="utf-8")
    assert "checks_per_loop * args.loops" in source
    assert "for loop in range(args.loops)" not in source
