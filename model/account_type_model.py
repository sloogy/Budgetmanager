from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class AccountType:
    id: int
    name: str
    kind: str  # 'income' | 'expense' | 'savings'
    color: str
    is_locked: bool


class AccountTypeModel:
    """Verwaltet Konti/Typen.

    WICHTIG:
    - Mindestens 3 Konti müssen immer existieren.
    - Typ-Name wird im System als Text in categories/budget/tracking verwendet.
      Beim Umbenennen wird deshalb per Cascade in diese Tabellen geschrieben.
    """

    KINDS = ("expense", "income", "savings")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list(self) -> list[AccountType]:
        cur = self.conn.execute(
            "SELECT id, name, kind, color, is_locked FROM account_types ORDER BY name COLLATE NOCASE"
        )
        out: list[AccountType] = []
        for r in cur.fetchall():
            out.append(
                AccountType(
                    int(r["id"]),
                    str(r["name"]),
                    str(r["kind"]),
                    str(r["color"] or ""),
                    bool(r["is_locked"]),
                )
            )
        return out

    def names(self) -> list[str]:
        return [t.name for t in self.list()]

    def kind_map(self) -> dict[str, str]:
        return {t.name: t.kind for t in self.list()}

    def create(self, name: str, kind: str, color: str = "") -> int:
        name = (name or "").strip()
        if not name:
            raise ValueError("Name darf nicht leer sein")
        if kind not in self.KINDS:
            raise ValueError("Ungültiger Typ-Kind")
        cur = self.conn.execute(
            "INSERT INTO account_types(name, kind, color, is_locked) VALUES(?,?,?,0)",
            (name, kind, color or ""),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update(self, type_id: int, *, name: str | None = None, kind: str | None = None, color: str | None = None) -> None:
        fields: list[str] = []
        params: list[object] = []
        if name is not None:
            fields.append("name=?")
            params.append((name or "").strip())
        if kind is not None:
            if kind not in self.KINDS:
                raise ValueError("Ungültiger Typ-Kind")
            fields.append("kind=?")
            params.append(kind)
        if color is not None:
            fields.append("color=?")
            params.append(color or "")
        if not fields:
            return
        params.append(int(type_id))
        self.conn.execute(f"UPDATE account_types SET {', '.join(fields)} WHERE id=?", params)
        self.conn.commit()

    def rename_and_cascade(self, old_name: str, new_name: str) -> None:
        old_name = (old_name or "").strip()
        new_name = (new_name or "").strip()
        if not old_name or not new_name:
            raise ValueError("Ungültiger Name")
        if old_name == new_name:
            return
        self.conn.execute("UPDATE account_types SET name=? WHERE name=?", (new_name, old_name))
        self.conn.execute("UPDATE categories SET typ=? WHERE typ=?", (new_name, old_name))
        self.conn.execute("UPDATE budget SET typ=? WHERE typ=?", (new_name, old_name))
        self.conn.execute("UPDATE tracking SET typ=? WHERE typ=?", (new_name, old_name))
        self.conn.commit()

    def delete(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        row = self.conn.execute(
            "SELECT id, is_locked FROM account_types WHERE name=?", (name,)
        ).fetchone()
        if not row:
            return
        if bool(row["is_locked"]):
            raise ValueError("Dieser Typ ist gesperrt und kann nicht gelöscht werden")

        # Nicht löschen, wenn noch Daten daran hängen
        c1 = self.conn.execute("SELECT 1 FROM categories WHERE typ=? LIMIT 1", (name,)).fetchone()
        c2 = self.conn.execute("SELECT 1 FROM budget WHERE typ=? LIMIT 1", (name,)).fetchone()
        c3 = self.conn.execute("SELECT 1 FROM tracking WHERE typ=? LIMIT 1", (name,)).fetchone()
        if c1 or c2 or c3:
            raise ValueError("Typ wird noch verwendet. Bitte zuerst Kategorien/Budget/Tracking umstellen.")

        self.conn.execute("DELETE FROM account_types WHERE name=?", (name,))
        self.conn.commit()
