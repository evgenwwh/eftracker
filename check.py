"""Одна команда перевірки: імпорт обох виписок, bean-check обох обліків і контрольні цифри.

Контрольні цифри змінних витрат (без тегу #fixed) взяті з умови завдання.
Запуск: uv run python check.py
"""
import importlib
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import beanquery

ROOT = Path(__file__).parent
EXPECTED = {
    "olia": {8: Decimal("2195.21"), 9: Decimal("2582.42")},
    "marko": {8: Decimal("1855.57"), 9: Decimal("2432.83")},
}
QUERY = (
    "SELECT month, sum(number) WHERE root(account, 1) = 'Expenses' "
    "AND NOT 'fixed' IN tags AND year = 2026 GROUP BY month ORDER BY month"
)


def main():
    importlib.import_module("import").main()
    ok = True
    for name, expected in EXPECTED.items():
        ledger = ROOT / "ledger" / f"{name}.beancount"
        result = subprocess.run(["bean-check", str(ledger)], capture_output=True, text=True)
        if result.returncode or result.stdout or result.stderr:
            ok = False
            print(f"{name}: bean-check знайшов помилки\n{result.stdout}{result.stderr}")
        else:
            print(f"{name}: bean-check без повідомлень")
        rows = dict(beanquery.connect(f"beancount:{ledger}").execute(QUERY).fetchall())
        for month, value in expected.items():
            got = rows.get(month, Decimal(0))
            mark = "збігається" if got == value else f"НЕ збігається, очікується {value}"
            ok &= got == value
            print(f"  змінні витрати, місяць {month}: {got} зл, {mark}")
    print("Усе збігається" if ok else "Є розбіжності")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
