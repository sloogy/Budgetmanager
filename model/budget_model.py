from __future__ import annotations
import sqlite3
from dataclasses import dataclass

@dataclass(frozen=True)
class BudgetRow:
    year: int
    month: int
    typ: str
    category: str
    amount: float

class BudgetModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn=conn

    def set_amount(self, year:int, month:int, typ:str, category:str, amount:float) -> None:
        self.conn.execute(
            "INSERT INTO budget(year,month,typ,category,amount) VALUES(?,?,?,?,?) "
            "ON CONFLICT(year,month,typ,category) DO UPDATE SET amount=excluded.amount",
            (int(year), int(month), typ, category, float(amount)),
        )
        self.conn.commit()

    def get_matrix(self, year:int, typ:str) -> dict[str, dict[int,float]]:
        cur=self.conn.execute(
            "SELECT month, category, amount FROM budget WHERE year=? AND typ=?",
            (int(year), typ),
        )
        matrix={}
        for r in cur.fetchall():
            matrix.setdefault(r["category"], {})[int(r["month"])]=float(r["amount"])
        return matrix

    def years(self) -> list[int]:
        cur=self.conn.execute("SELECT DISTINCT year FROM budget ORDER BY year")
        return [int(r[0]) for r in cur.fetchall()]

    def seed_year_from_categories(self, year:int, typ:str, categories:list[str], amount:float=0.0) -> None:
        cur=self.conn.cursor()
        for cat in categories:
            for m in range(1,13):
                cur.execute(
                    "INSERT OR IGNORE INTO budget(year,month,typ,category,amount) VALUES(?,?,?,?,?)",
                    (int(year), int(m), typ, cat, float(amount)),
                )
        self.conn.commit()

    def delete_category_for_year(self, year:int, typ:str, category:str) -> None:
        self.conn.execute(
            "DELETE FROM budget WHERE year=? AND typ=? AND category=?",
            (int(year), typ, category),
        )
        self.conn.commit()

    def delete_category_all_years(self, typ:str, category:str) -> None:
        self.conn.execute(
            "DELETE FROM budget WHERE typ=? AND category=?",
            (typ, category),
        )
        self.conn.commit()


    def get_amount(self, year:int, month:int, typ:str, category:str) -> float:
        row = self.conn.execute(
            "SELECT amount FROM budget WHERE year=? AND month=? AND typ=? AND category=?",
            (int(year), int(month), typ, category),
        ).fetchone()
        return float(row["amount"]) if row else 0.0

    def sum_by_typ(self, year:int, month:int | None = None) -> dict[str, float]:
        if month is None:
            cur = self.conn.execute(
                "SELECT typ, SUM(amount) AS s FROM budget WHERE year=? GROUP BY typ",
                (int(year),),
            )
        else:
            cur = self.conn.execute(
                "SELECT typ, SUM(amount) AS s FROM budget WHERE year=? AND month=? GROUP BY typ",
                (int(year), int(month)),
            )
        return {str(r["typ"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_category(self, year:int, typ:str, month:int | None = None) -> dict[str, float]:
        if month is None:
            cur = self.conn.execute(
                "SELECT category, SUM(amount) AS s FROM budget WHERE year=? AND typ=? GROUP BY category ORDER BY ABS(s) DESC",
                (int(year), typ),
            )
        else:
            cur = self.conn.execute(
                "SELECT category, SUM(amount) AS s FROM budget WHERE year=? AND month=? AND typ=? GROUP BY category ORDER BY ABS(s) DESC",
                (int(year), int(month), typ),
            )
        return {str(r["category"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_month(self, year:int, typ: str | None = None) -> dict[int, float]:
        if typ is None:
            cur = self.conn.execute(
                "SELECT month AS m, SUM(amount) AS s FROM budget WHERE year=? GROUP BY m ORDER BY m",
                (int(year),),
            )
        else:
            cur = self.conn.execute(
                "SELECT month AS m, SUM(amount) AS s FROM budget WHERE year=? AND typ=? GROUP BY m ORDER BY m",
                (int(year), typ),
            )
        out = {int(r["m"]): float(r["s"] or 0.0) for r in cur.fetchall()}
        for m in range(1,13):
            out.setdefault(m, 0.0)
        return out




    def sum_by_typ_all(self, month:int | None = None) -> dict[str, float]:
        if month is None:
            cur = self.conn.execute("SELECT typ, SUM(amount) AS s FROM budget GROUP BY typ")
        else:
            cur = self.conn.execute(
                "SELECT typ, SUM(amount) AS s FROM budget WHERE month=? GROUP BY typ",
                (int(month),),
            )
        return {str(r["typ"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_category_all(self, typ:str, month:int | None = None) -> dict[str, float]:
        if month is None:
            cur = self.conn.execute(
                "SELECT category, SUM(amount) AS s FROM budget WHERE typ=? GROUP BY category ORDER BY ABS(s) DESC",
                (typ,),
            )
        else:
            cur = self.conn.execute(
                "SELECT category, SUM(amount) AS s FROM budget WHERE month=? AND typ=? GROUP BY category ORDER BY ABS(s) DESC",
                (int(month), typ),
            )
        return {str(r["category"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_month_all(self, typ: str | None = None) -> dict[int, float]:
        if typ is None:
            cur = self.conn.execute("SELECT month AS m, SUM(amount) AS s FROM budget GROUP BY m ORDER BY m")
        else:
            cur = self.conn.execute(
                "SELECT month AS m, SUM(amount) AS s FROM budget WHERE typ=? GROUP BY m ORDER BY m",
                (typ,),
            )
        out = {int(r["m"]): float(r["s"] or 0.0) for r in cur.fetchall()}
        for m in range(1,13):
            out.setdefault(m, 0.0)
        return out

    def copy_year(self, src_year:int, dst_year:int, carry_amounts:bool=True, typ: str | None = None) -> None:
        if typ is None:
            if carry_amounts:
                self.conn.execute(
                    "INSERT OR REPLACE INTO budget(year,month,typ,category,amount) "
                    "SELECT ?, month, typ, category, amount FROM budget WHERE year=?",
                    (int(dst_year), int(src_year)),
                )
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO budget(year,month,typ,category,amount) "
                    "SELECT ?, month, typ, category, 0 FROM budget WHERE year=?",
                    (int(dst_year), int(src_year)),
                )
        else:
            if carry_amounts:
                self.conn.execute(
                    "INSERT OR REPLACE INTO budget(year,month,typ,category,amount) "
                    "SELECT ?, month, typ, category, amount FROM budget WHERE year=? AND typ=?",
                    (int(dst_year), int(src_year), typ),
                )
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO budget(year,month,typ,category,amount) "
                    "SELECT ?, month, typ, category, 0 FROM budget WHERE year=? AND typ=?",
                    (int(dst_year), int(src_year), typ),
                )
        self.conn.commit()
