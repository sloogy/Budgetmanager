"""Kompatibler Einstiegspunkt für den Bankimport-Dialog.

Die Implementierung liegt in ``bank_import_dialog_v2``. Der Importpfad bleibt
stabil, damit bestehende Menü- und Testaufrufe unverändert funktionieren.
"""
from views.bank_import_dialog_v2 import BankImportDialog

__all__ = ["BankImportDialog"]
