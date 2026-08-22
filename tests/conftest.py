from __future__ import annotations

import sys
from pathlib import Path

# Stabilisiert beide Aufrufarten:
#   python -m pytest ...  und  pytest ...
# Einige pytest-Wrapper setzen den Projekt-Root nicht automatisch auf sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    """Keep release tests fast without weakening production crypto defaults."""
    import model.crypto as crypto
    import model.user_model as user_model

    test_iterations = 1_000
    crypto.PBKDF2_ITERATIONS = test_iterations
    user_model.PBKDF2_ITERATIONS = test_iterations


def pytest_runtest_teardown(item, nextitem):
    """Finalisiert zyklische Testobjekte pro Test, damit Ressourcenlecks sofort auffallen."""
    import gc

    gc.collect()


# ── Loop 31: Das Bruecken-Register gehoert nie in die echte Nutzerkonfiguration ─
# Ohne diese Weiche schreibt jeder Test, der einen Brueckenordner aufloest, in
# ~/.config/fpm-suite/bridges.json - und traegt tmp-Pfade ein, die es danach
# nicht mehr gibt.
import pytest


@pytest.fixture(autouse=True)
def _bruecken_register_isolieren(tmp_path_factory, monkeypatch):
    ziel = tmp_path_factory.mktemp("bridge-registry") / "bridges.json"
    monkeypatch.setenv("FPM_SUITE_BRIDGE_REGISTRY", str(ziel))
    yield
