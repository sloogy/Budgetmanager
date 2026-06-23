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
