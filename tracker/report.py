"""Сторінка звіту Марка й Олі: дохід, витрати, норма заощаджень, фіксовані і змінні, категорії по місяцях.

Цифри беремо зі збережених запитів обох обліків. Дані за всі місяці лежать у сторінці,
тож перемикання людей і місяців відбувається в браузері без запитів до сервера.
Шаблон і стилі в tracker/page.html.
"""
import calendar
import json
from datetime import date
from pathlib import Path

import beanquery
from beancount import loader
from beancount.core import data

from tracker.ledger import expense_accounts

TEMPLATE = Path(__file__).with_name("page.html")
CATEGORY_NAMES = {"Косметика-Побут": "Косметика і побут"}


def category_label(account):
    name = account.split(":", 1)[1]
    return CATEGORY_NAMES.get(name) or name.replace("-", " ").capitalize()


def person_data(ledger, title, gen):
    """Дані однієї людини по місяцях зі збережених запитів її обліку."""
    entries, errors, _ = loader.load_file(str(ledger))
    if errors:
        raise SystemExit(f"Облік {ledger.name} має помилки, спершу виправте їх: {errors[0]}")
    # Межа неповного місяця: остання операція з виписки банку, а не вручну додана витрата.
    bank_last = max(
        e.date for e in entries
        if isinstance(e, data.Transaction) and Path(e.meta["filename"]).name.startswith("transactions-")
    )
    sql = {e.name: e.query_string for e in entries if isinstance(e, data.Query)}
    conn = beanquery.connect(f"beancount:{ledger}")
    result = {name: conn.execute(sql[name]).fetchall() for name in ("категорії", "заощадження", "фіксовані-змінні")}

    months = {}
    for year, month, income, *_ in result["заощадження"]:
        days = calendar.monthrange(year, month)[1]
        last = days if (year, month) < (bank_last.year, bank_last.month) else min(bank_last.day, days)
        months[f"{year}-{month:02d}"] = {"income": float(income), "fixed": 0.0, "lastDay": last, "days": days, "cats": {}}
    for year, month, fixed, *_ in result["фіксовані-змінні"]:
        months[f"{year}-{month:02d}"]["fixed"] = float(fixed)
    for year, month, account, amount in result["категорії"]:
        months[f"{year}-{month:02d}"]["cats"][category_label(account)] = float(amount)

    chips = [{"label": category_label(a), "account": a} for a in expense_accounts(Path(ledger))]
    return {"title": title, "gen": gen, "months": months, "chips": chips}


def render(people):
    """people: {"marko": (облік, заголовок, родовий відмінок імені), ...} → готова HTML-сторінка."""
    payload = {key: person_data(*info) for key, info in people.items()}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("%%DATA%%", blob)
        .replace("%%TODAY%%", date.today().strftime("%d.%m.%Y"))
    )
