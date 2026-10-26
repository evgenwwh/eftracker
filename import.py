"""Перетворює виписки з data/*.csv на облік Олі і Марка за правилами з rules.csv.

Файли ledger/transactions-*.beancount щоразу перезаписуються повністю, руками їх не правимо.
Запуск: uv run python import.py
"""
from pathlib import Path

from tracker.banks import load_statements
from tracker.ledger import ensure_manual, load_rules, write_ledger

ROOT = Path(__file__).parent
DATA = ROOT / "data"
LEDGER = ROOT / "ledger"
PEOPLE = ("olia", "marko")


def main():
    rules = load_rules(ROOT / "rules.csv")
    statements = load_statements(DATA)
    for name in PEOPLE:
        ensure_manual(LEDGER / f"manual-{name}.beancount")
        count, checks = write_ledger(statements[name], rules, LEDGER / f"transactions-{name}.beancount")
        print(f"{name}: операцій {count}, перевірок залишку {checks}")


if __name__ == "__main__":
    main()
