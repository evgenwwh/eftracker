"""Читання виписок двох банків в однаковий вигляд: день, опис, сума, залишок після операції.

Порядок рядків не сортуємо: залишок у виписці рахується саме в порядку банку.
Однаковий рядок з кількох виписок рахуємо один раз.
"""
import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

CURRENCY = "PLN"
MARKO_HEADER = "Historia operacji"
MARKO_COLUMNS = "Data operacji;Data księgowania;Typ operacji;Opis;Kwota;Saldo po operacji"


def owner(path: Path) -> str:
    """Чия виписка: у банку Марка файл починається з «Historia operacji»."""
    with open(path, encoding="utf-8") as f:
        return "marko" if f.readline().strip() == MARKO_HEADER else "olia"


def pl_amount(text):
    """«-1 234,56» у Decimal: пробіли між тисячами прибираємо, кома стає крапкою."""
    return Decimal(text.replace(" ", "").replace(" ", "").replace(",", "."))


def read_olia(path, seen):
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["Currency"] != CURRENCY or row["State"] != "COMPLETED":
                raise SystemExit(f"{path.name}: очікується COMPLETED у {CURRENCY}, а тут {row}")
            if Decimal(row["Fee"]) != 0:
                raise SystemExit(f"{path.name}: комісія в операції {row}, її ще не підтримано")
            key = (row["Completed Date"], row["Description"], row["Amount"], row["Balance"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "day": datetime.fromisoformat(row["Completed Date"]).date(),
                "description": row["Description"],
                "amount": Decimal(row["Amount"]),
                "balance": Decimal(row["Balance"]),
            })
    return rows


def read_marko(path, seen):
    """Банк Марка пише нові операції зверху, тому список розвертаємо. Інакше порядок не чіпаємо."""
    lines = path.read_text(encoding="utf-8").splitlines()
    currency = next(line.split(";")[1] for line in lines if line.startswith("Waluta;"))
    if currency != CURRENCY:
        raise SystemExit(f"{path.name}: очікується {CURRENCY}, а тут {currency}")
    rows = []
    for record in csv.reader(lines[lines.index(MARKO_COLUMNS) + 1:], delimiter=";"):
        if not record:
            continue
        booked, description, amount, balance = record[1], record[3], record[4], record[5]
        key = (booked, description, amount, balance)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "day": datetime.strptime(booked, "%d.%m.%Y").date(),
            "description": description,
            "amount": pl_amount(amount),
            "balance": pl_amount(balance),
        })
    return rows[::-1]


READERS = {"olia": read_olia, "marko": read_marko}


def load_statements(data_dir: Path):
    """Усі виписки з data_dir, розкладені за власником."""
    rows = {name: [] for name in READERS}
    seen = {name: set() for name in READERS}
    for path in sorted(data_dir.glob("*.csv")):
        name = owner(path)
        rows[name] += READERS[name](path, seen[name])
    return rows
