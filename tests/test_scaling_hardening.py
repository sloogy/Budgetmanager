from __future__ import annotations

import os
from pathlib import Path


def test_qt_scaling_defaults_do_not_force_absolute_scale(monkeypatch):
    """Portable/Windows/Linux sollen System-DPI nutzen, nicht eine harte Groesse."""
    monkeypatch.delenv("QT_ENABLE_HIGHDPI_SCALING", raising=False)
    monkeypatch.delenv("QT_AUTO_SCREEN_SCALE_FACTOR", raising=False)
    monkeypatch.delenv("QT_SCALE_FACTOR_ROUNDING_POLICY", raising=False)
    monkeypatch.delenv("QT_SCALE_FACTOR", raising=False)

    from utils.ui_scaling import configure_qt_scaling_environment

    configure_qt_scaling_environment()

    assert os.environ["QT_ENABLE_HIGHDPI_SCALING"] == "1"
    assert os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] == "1"
    assert os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] == "PassThrough"
    assert "QT_SCALE_FACTOR" not in os.environ


def test_portable_starters_set_fractional_scaling_policy():
    builder = Path("tools/build_release_assets.py").read_text(encoding="utf-8")
    assert 'QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough' in builder
    assert 'QT_SCALE_FACTOR_ROUNDING_POLICY:-PassThrough' in builder
