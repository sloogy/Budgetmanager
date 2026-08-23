"""Kompatibler Einstiegspunkt für den Bankimport-Dialog.

Die Hauptimplementierung liegt in ``bank_import_dialog_v2``. Diese dünne
Kompatibilitätsschicht hält den bisherigen Importpfad stabil und korrigiert
den Refresh nach einem Typwechsel.
"""
from views.bank_import_dialog_v2 import BankImportDialog as _BankImportDialogV2


class BankImportDialog(_BankImportDialogV2):
    def _type_changed(self, row: int) -> None:
        if self._updating_row:
            return
        self._updating_row = True
        try:
            self._set_prediction_for_row(row, replace_tags=True)
        finally:
            self._updating_row = False
        self._refresh_effective_view()


__all__ = ["BankImportDialog"]
