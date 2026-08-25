"""Zentrale Logging-Konfiguration für den Budgetmanager."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_level: int = logging.INFO, log_file: str | None = None) -> None:
    """Initialisiert Konsolen- und optionales Datei-Logging.

    Aufruf einmalig in main() vor allem anderen Code:

        from model.logging_config import setup_logging
        setup_logging(log_file="data/budgetmanager.log")
    """
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # Root auf DEBUG – Handler filtern selbst

    # Konsole
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        # Der StreamHandler erbt die Kodierung von sys.stderr - auf einer
        # Windows-Konsole cp850/cp1252. Die App loggt reichlich deutsche Texte,
        # der Updater zusaetzlich ❌, ✓ und ⟲: Jede solche Zeile loeste dort
        # einen UnicodeEncodeError im Handler aus, den das logging-Modul
        # abfaengt und durch "--- Logging error ---" ersetzt. Verloren gingen
        # damit genau die Diagnosezeilen, die man bei einem Windows-Problem
        # braucht - waehrend der Datei-Handler daneben seit jeher
        # encoding="utf-8" hat.
        #
        # Bewusst ueber utils/console_encoding.py und nicht ueber
        # updater/common.py: Dieselbe Funktion liegt dort, aber das Modul zieht
        # requests und packaging mit - eine Abhaengigkeit, die im Startpfad
        # jeder Logging-Einrichtung nichts zu suchen hat.
        from utils.console_encoding import enable_utf8_console

        enable_utf8_console()

        console = logging.StreamHandler()
        console.setLevel(log_level)
        console.setFormatter(formatter)
        root.addHandler(console)

    # Rotierende Log-Datei (max 10 MB, 5 Backups)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
