"""Сторінка звіту з трьома відповідями по місяцях: категорії, заощадження, фіксовані і змінні витрати.

Цифри беремо зі збережених запитів обліку при кожному виклику, тож вручну додані витрати видно одразу.
Сторінка самодостатня і працює без інтернету.
"""
import calendar
from datetime import date
from html import escape
from pathlib import Path

import beanquery
from beancount import loader
from beancount.core import data

MONTHS = ["січень", "лютий", "березень", "квітень", "травень", "червень",
          "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"]
MONTHS_OF = ["січня", "лютого", "березня", "квітня", "травня", "червня",
             "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
CATEGORY_NAMES = {"Косметика-Побут": "Косметика і побут"}
NBSP = " "


def run_saved_queries(ledger):
    entries, errors, _ = loader.load_file(str(ledger))
    if errors:
        raise SystemExit(f"Облік має помилки, спершу виправте їх: {errors[0]}")
    last_day = max(e.date for e in entries if isinstance(e, data.Transaction))
    sql = {e.name: e.query_string for e in entries if isinstance(e, data.Query)}
    conn = beanquery.connect(f"beancount:{ledger}")
    return last_day, {name: conn.execute(sql[name]).fetchall() for name in sql}


def money(value):
    return f"{value:,.2f}".replace(",", NBSP).replace(".", ",") + NBSP + "зл"


def percent(value):
    return f"{value:.1f}".replace(".", ",") + NBSP + "%"


def day_text(day):
    return f"{day.day} {MONTHS_OF[day.month - 1]}"


def category_label(account):
    name = account.split(":", 1)[1]
    return CATEGORY_NAMES.get(name) or name.replace("-", " ").capitalize()


def block(question, figure, caption, chart, conclusion):
    return (
        f'<article class="block"><h2>{question}</h2>'
        f'<p class="figure">{figure}</p><p class="caption">{caption}</p>'
        f'{chart}<p class="conclusion">{conclusion}</p></article>'
    )


def categories_block(items, top):
    total = sum(r[3] for r in items)
    bars = "".join(
        f'<li><span class="name">{escape(category_label(r[2]))}</span>'
        f'<span class="track"><span class="fill s1" style="width:{r[3] / top * 100:.2f}%"></span></span>'
        f'<span class="val">{money(r[3])}</span></li>'
        for r in items
    )
    if len(items) < 2:
        conclusion = f"Усі витрати в категорії {category_label(items[0][2]).lower()}."
        return block("Скільки грошей іде на кожну категорію витрат?", money(total), "усього витрат за місяць",
                     f'<ul class="bars">{bars}</ul>', conclusion)
    first, second = items[0], items[1]
    conclusion = (
        f"Найбільше йде на {category_label(first[2]).lower()}: {money(first[3])}, "
        f"це {percent(first[3] / total * 100)} усіх витрат. Далі {category_label(second[2]).lower()}: {money(second[3])}."
    )
    return block("Скільки грошей іде на кожну категорію витрат?", money(total), "усього витрат за місяць",
                 f'<ul class="bars">{bars}</ul>', conclusion)


def savings_block(row, previous, incomplete, last_op):
    _, _, income, expenses, saved, rate, _ = row
    if rate is None:
        chart = (f'<div class="legend"><span><i class="dot dot-muted"></i>Витрати {money(expenses)}</span></div>')
        conclusion = f"Доходу за цей місяць ще немає, тому частку заощаджень порахувати не можна. Дані станом на {day_text(last_op)}."
        return block("Яку частку доходу відкладено?", "немає доходу", "у цьому місяці", chart, conclusion)
    chart = (
        f'<span class="track tall"><span class="fill s1" style="width:{max(rate, 0):.1f}%"></span></span>'
        f'<div class="legend"><span><i class="dot s1"></i>Відкладено {money(saved)}</span>'
        f'<span><i class="dot dot-muted"></i>Витрати {money(expenses)}</span></div>'
    )
    conclusion = f"З доходу {money(income)} відкладено {money(saved)}, це {percent(rate)}"
    if incomplete:
        conclusion += f"; це дані станом на {day_text(last_op)}, місяць ще не завершився, тож порівнювати його з попередніми рано."
    elif previous is not None:
        diff = rate - previous[5]
        word = "більше" if diff > 0 else "менше"
        conclusion += f"; це на {abs(diff):.1f}".replace(".", ",") + f"{NBSP}п.п. {word}, ніж у попередньому місяці."
    else:
        conclusion += "."
    return block("Яку частку доходу відкладено?", percent(rate), "доходу відкладено", chart, conclusion)


def fixed_block(row, top):
    _, _, fixed, managed, total, fixed_share = row
    chart = (
        f'<div class="stack" style="width:{total / top * 100:.2f}%">'
        f'<span class="seg s1" style="flex:{fixed}"></span><span class="seg s2" style="flex:{managed}"></span></div>'
        f'<div class="legend"><span><i class="dot s1"></i>Фіксовані {money(fixed)}</span>'
        f'<span><i class="dot s2"></i>Змінні {money(managed)}</span></div>'
    )
    conclusion = (
        f"Фіксовані витрати становлять {money(fixed)}, змінні {money(managed)}. "
        f"Скоротити можна саме змінні."
    )
    return block("Скільки витрат фіксовані, а скільки змінні?", percent(fixed_share), "витрат фіксовані", chart, conclusion)


def uncategorized_warning(rows):
    if not rows:
        return ""
    count = sum(r[3] for r in rows)
    total = sum(abs(r[4]) for r in rows)
    return (f'<p class="warning">Є {count} операцій без категорії на {money(total)}. '
            f"Для них потрібні правила в rules.csv.</p>")


PAGE = """<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>%%TITLE%%</title>
<style>
:root {
  color-scheme: light;
  --surface: #fcfcfb; --card: #ffffff; --line: #e4e3df;
  --text: #0b0b0b; --text-2: #52514e;
  --s1: #2a78d6; --s2: #eb6834; --track: #ecebe7; --warn: #8a4b00; --warn-bg: #fff4e0;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #1a1a19; --card: #222221; --line: #343432;
    --text: #f0efec; --text-2: #c3c2b7;
    --s1: #3987e5; --s2: #d95926; --track: #2d2d2b; --warn: #f0c27a; --warn-bg: #3a2e18;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #1a1a19; --card: #222221; --line: #343432;
  --text: #f0efec; --text-2: #c3c2b7;
  --s1: #3987e5; --s2: #d95926; --track: #2d2d2b; --warn: #f0c27a; --warn-bg: #3a2e18;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--text);
  font: 16px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.7rem; margin: 0 0 4px; }
h2 { font-size: 1.05rem; margin: 0 0 12px; }
.lead, .note { color: var(--text-2); margin: 0; }
.note { margin-top: 28px; font-size: .9rem; }
.switcher { position: sticky; top: 0; z-index: 1; background: var(--surface); padding: 14px 0 10px;
  display: flex; flex-wrap: wrap; gap: 8px; }
.switcher[hidden], .month[hidden] { display: none; }
.switcher button { font: inherit; font-size: .95rem; color: var(--text); background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: 6px 16px; cursor: pointer; }
.switcher button[aria-pressed="true"] { border-color: var(--s1); box-shadow: inset 0 0 0 1px var(--s1); font-weight: 600; }
.switcher button:focus-visible { outline: 2px solid var(--s1); outline-offset: 2px; }
.month { margin-top: 8px; }
.month > header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; margin: 8px 0 12px; }
.month > header h2 { font-size: 1.3rem; margin: 0; }
.badge { font-size: .8rem; font-weight: 500; color: var(--text-2); border: 1px solid var(--line);
  border-radius: 999px; padding: 1px 10px; white-space: nowrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
.block { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px;
  display: flex; flex-direction: column; }
.figure { font-size: 2.3rem; font-weight: 650; margin: 0; line-height: 1.1; font-variant-numeric: tabular-nums; }
.caption { color: var(--text-2); margin: 2px 0 14px; }
.conclusion { margin: auto 0 0; padding-top: 12px; border-top: 1px solid var(--line); }
.bars + .conclusion, .legend + .conclusion { margin-top: 14px; }
.bars { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.bars li { display: grid; grid-template-columns: 8.5rem 1fr 6.5rem; gap: 8px; align-items: center; font-size: .9rem; }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.val { font-variant-numeric: tabular-nums; text-align: right; }
.track { display: block; height: 8px; background: var(--track); border-radius: 4px; overflow: hidden; }
.track.tall { height: 14px; }
.fill { display: block; height: 100%; border-radius: 0 4px 4px 0; }
.s1 { background: var(--s1); }
.s2 { background: var(--s2); }
.stack { display: flex; gap: 2px; height: 14px; min-width: 40px; }
.seg { display: block; height: 100%; }
.seg:first-child { border-radius: 4px 0 0 4px; }
.seg:last-child { border-radius: 0 4px 4px 0; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 10px; font-size: .9rem; color: var(--text-2);
  font-variant-numeric: tabular-nums; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; }
.dot-muted { background: var(--track); border: 1px solid var(--line); }
.people { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
.people a { color: var(--text); text-decoration: none; border: 1px solid var(--line); background: var(--card);
  border-radius: 999px; padding: 6px 16px; font-size: .95rem; }
.people a[aria-current="page"] { border-color: var(--s1); box-shadow: inset 0 0 0 1px var(--s1); font-weight: 600; }
.people .add { margin-left: auto; background: var(--s1); border-color: var(--s1); color: #fff; font-weight: 600; }
.warning { margin: 16px 0 0; padding: 10px 14px; border-radius: 8px; background: var(--warn-bg); color: var(--warn); }
@media (max-width: 480px) {
  .bars li { grid-template-columns: 6.5rem 1fr 6rem; }
  .name { white-space: normal; line-height: 1.2; }
}
</style>
</head>
<body>
<main>
%%NAV%%
<h1>%%TITLE%%</h1>
<p class="lead">Період: з %%FIRST%% до %%LAST%%. Усі суми в злотих.</p>
<nav class="switcher" aria-label="Місяць" data-default="%%DEFAULT%%" hidden>%%BUTTONS%%</nav>
%%MONTHS%%
%%WARNING%%
<p class="note">Джерело: %%SOURCE%%, збережені запити «категорії», «заощадження», «фіксовані-змінні». Звіт сформовано %%TODAY%%.</p>
</main>
<script>
(function () {
  var nav = document.querySelector(".switcher");
  var buttons = [].slice.call(nav.querySelectorAll("button"));
  var panels = [].slice.call(document.querySelectorAll(".month"));
  function has(key) { return panels.some(function (p) { return p.dataset.month === key; }); }
  function show(key) {
    if (!has(key)) return;
    panels.forEach(function (p) { p.hidden = p.dataset.month !== key; });
    buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.pick === key)); });
    try { history.replaceState(null, "", "#" + key); } catch (e) {}
  }
  buttons.forEach(function (b) { b.addEventListener("click", function () { show(b.dataset.pick); }); });
  nav.hidden = false;
  var wanted = location.hash.slice(1);
  show(has(wanted) ? wanted : nav.dataset.default);
})();
</script>
</body>
</html>
"""


def render(ledger, title, nav=""):
    """HTML-сторінка звіту для одного обліку: три питання по місяцях з перемикачем."""
    last_day, result = run_saved_queries(ledger)
    categories, fixed = result["категорії"], result["фіксовані-змінні"]
    savings = sorted(result["заощадження"], key=lambda r: (r[0], r[1]))

    top_category = max(r[3] for r in categories)
    top_total = max(r[4] for r in fixed)
    fixed_by_month = {(r[0], r[1]): r for r in fixed}

    buttons, months, default = [], [], None
    for index, row in enumerate(savings):
        year, month, last_op = row[0], row[1], row[6]
        key = f"{year}-{month:02d}"
        incomplete = last_day < date(year, month, calendar.monthrange(year, month)[1])
        if not incomplete:
            default = key
        label = MONTHS[month - 1].capitalize() + (" · неповний" if incomplete else "")
        buttons.append(f'<button type="button" data-pick="{key}" aria-pressed="false">{label}</button>')

        badge = (f'неповний місяць, дані до {day_text(last_op)}' if incomplete else "повний місяць")
        items = [r for r in categories if (r[0], r[1]) == (year, month)]
        blocks = (
            categories_block(items, top_category)
            + savings_block(row, savings[index - 1] if index else None, incomplete, last_op)
            + fixed_block(fixed_by_month[(year, month)], top_total)
        )
        months.append(
            f'<section class="month" data-month="{key}"><header>'
            f'<h2>{MONTHS[month - 1].capitalize()} {year}</h2><span class="badge">{badge}</span></header>'
            f'<div class="grid">{blocks}</div></section>'
        )

    last_row = savings[-1]
    first_day = date(savings[0][0], savings[0][1], 1)
    page = (
        PAGE.replace("%%FIRST%%", f"{day_text(first_day)} {first_day.year}")
        .replace("%%LAST%%", f"{day_text(last_day)} {last_day.year}")
        .replace("%%DEFAULT%%", default or f"{last_row[0]}-{last_row[1]:02d}")
        .replace("%%BUTTONS%%", "".join(buttons))
        .replace("%%MONTHS%%", "\n".join(months))
        .replace("%%WARNING%%", uncategorized_warning(result["без-категорії"]))
        .replace("%%TODAY%%", date.today().strftime("%d.%m.%Y"))
        .replace("%%TITLE%%", escape(title))
        .replace("%%NAV%%", nav)
        .replace("%%SOURCE%%", f"ledger/{Path(ledger).name}")
    )
    return page
