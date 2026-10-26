"""Правила категорій і запис обліку Beancount з рядків виписки."""
import csv
from datetime import date, timedelta
from pathlib import Path

BANK = "Assets:Банк"
OPENING = "Equity:Початковий-Залишок"
UNCATEGORIZED_EXPENSE = "Expenses:Без-Категорії"
UNCATEGORIZED_INCOME = "Income:Інше"
CURRENCY = "PLN"


def load_rules(path: Path):
    """Правила з rules.csv: шаблон шукаємо в описі без урахування регістру, перемагає перше."""
    with open(path, encoding="utf-8", newline="") as f:
        return [
            (row["шаблон"].casefold(), row["рахунок"], row["фіксована"].strip() == "так")
            for row in csv.DictReader(f)
        ]


def categorize(description, amount, rules):
    text = description.casefold()
    for pattern, account, fixed in rules:
        if pattern in text:
            return account, fixed
    return (UNCATEGORIZED_INCOME if amount > 0 else UNCATEGORIZED_EXPENSE), False


def money(value):
    return f"{value:.2f} {CURRENCY}"


def write_ledger(rows, rules, path: Path):
    """Повністю перезаписує файл операцій: початковий залишок, операції, перевірки залишку."""
    if not rows:
        raise SystemExit(f"Для {path.name} немає жодної операції")

    first = rows[0]
    out = [
        "; Згенеровано import.py з data/*.csv і rules.csv. Не редагувати: файл перезаписується.",
        "",
        f'{first["day"] - timedelta(days=1)} * "Початковий залишок"',
        f"  {BANK}  {money(first['balance'] - first['amount'])}",
        f"  {OPENING}",
        "",
    ]
    for row in rows:
        account, fixed = categorize(row["description"], row["amount"], rules)
        narration = row["description"].replace('"', "'")
        tag = " #fixed" if fixed else ""
        out += [
            f'{row["day"]} * "{narration}"{tag}',
            f"  {BANK}  {money(row['amount'])}",
            f"  {account}",
            "",
        ]

    # Залишок за колонкою виписки: остання операція місяця в порядку банку.
    month_end = {}
    for row in rows:
        month_end[(row["day"].year, row["day"].month)] = (row["day"], row["balance"])
    last_month = max(month_end)
    for (year, month), (day, balance) in sorted(month_end.items()):
        if (year, month) == last_month:
            check_day = day + timedelta(days=1)
        else:
            check_day = date(year + month // 12, month % 12 + 1, 1)
        out += [f"{check_day} balance {BANK}  {money(balance)}", ""]

    path.write_text("\n".join(out), encoding="utf-8")
    return len(rows), len(month_end)


def ensure_manual(path: Path):
    """Файл для витрат, доданих у Fava кнопкою +. Створюємо порожнім, якщо його ще немає; імпорт його не чіпає."""
    if not path.exists():
        path.write_text("; Витрати, додані вручну через Fava (кнопка +). Імпорт цей файл не перезаписує.\n", encoding="utf-8")
