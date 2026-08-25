"""Aktiver Bankimport-Einstiegspunkt.

Seit UX-V4 ist die Runtime bewusst nur noch ein Alias. Die komplette aktive
Bedienlogik liegt in ``bank_import_dialog_v4``; die früheren V2/V3/Runtime-
Patchschichten bleiben nur als Legacy-/Migrationsreferenz im Repository.
"""

from views.bank_import_dialog_v4 import BankImportDialog

__all__ = ["BankImportDialog"]
