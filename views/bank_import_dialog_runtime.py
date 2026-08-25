"""Aktiver Bankimport-Einstiegspunkt.

Seit UX-V4 ist die Runtime bewusst nur noch ein Alias. Die komplette aktive
Bedienlogik liegt in ``bank_import_dialog_v4``; die früheren V2/V3/Runtime-
Patchschichten sind gelöscht. Dieses Modul bleibt als stabiler
Einstiegspunkt bestehen, damit Aufrufer nicht an einem Versionsnamen hängen.
"""

from views.bank_import_dialog_v4 import BankImportDialog

__all__ = ["BankImportDialog"]
