"""Трекер для PythonAnywhere: сторінка звіту Марка й Олі на /, Fava на /fava, усе за паролем.

Логін і пароль беремо лише зі змінних середовища TRACKER_USER і TRACKER_PASSWORD.
На сервері їх кладемо у файл ~/.tracker.env (рядки KEY=VALUE), у репозиторії їх немає.
Без цих змінних трекер не показує жодних даних.
"""
import base64
import hmac
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, urlsplit

from beancount import loader
from fava.application import create_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Request, Response

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = Path.home() / ".tracker.env"
# хто: (облік, заголовок сторінки, «звіт кого»)
PEOPLE = {
    "marko": (ROOT / "ledger" / "marko.beancount", "Фінанси Марка", "Марка"),
    "olia": (ROOT / "ledger" / "olia.beancount", "Фінанси Олі", "Олі"),
}


def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def require_password(app, user, password):
    expected = f"{user}:{password}".encode()

    def wrapped(environ, start_response):
        header = environ.get("HTTP_AUTHORIZATION", "")
        if header.startswith("Basic "):
            try:
                given = base64.b64decode(header[6:])
            except ValueError:
                given = b""
            if user and password and hmac.compare_digest(given, expected):
                return app(environ, start_response)
        start_response("401 Unauthorized", [
            ("WWW-Authenticate", 'Basic realm="tracker", charset="UTF-8"'),
            ("Content-Type", "text/plain; charset=utf-8"),
        ])
        return ["Потрібен вхід".encode()]

    return wrapped


_cache = {}


def ledger_version():
    """Час останньої зміни файлів обліку: після нової витрати сторінку треба перерахувати."""
    return max(path.stat().st_mtime for path in (ROOT / "ledger").glob("*.beancount"))


def report_page():
    """Готова сторінка з пам’яті; перераховуємо лише тоді, коли змінився облік."""
    from tracker.report import render

    version = ledger_version()
    if _cache.get("version") != version:
        _cache.update(version=version, page=render(PEOPLE))
    return _cache["page"]


def add_expense(request):
    """Приймає форму «Додати витрату»: перевіряє, дописує в manual-файл, перевіряє облік, інакше відкочує."""
    from tracker.ledger import expense_accounts, manual_entry

    origin = request.headers.get("Origin") or request.headers.get("Referer") or ""
    if urlsplit(origin).netloc != request.host:
        return Response("Форма приймається лише з цього сайту", status=403)
    who = request.form.get("who", "")
    if who not in PEOPLE:
        return Response("Невідомий користувач", status=400)
    ledger = PEOPLE[who][0]
    account = request.form.get("account", "")
    if account not in expense_accounts(ledger):
        return Response("Невідома категорія", status=400)
    try:
        amount = Decimal(request.form.get("amount", "").replace(",", ".").replace(" ", ""))
        day = date.fromisoformat(request.form.get("date", ""))
    except (InvalidOperation, ValueError):
        return Response("Неправильна сума або дата", status=400)
    if not (0 < amount <= 100000) or amount != amount.quantize(Decimal("0.01")):
        return Response("Сума має бути від 0,01 до 100 000 зл", status=400)

    manual = ROOT / "ledger" / f"manual-{who}.beancount"
    before = manual.read_text(encoding="utf-8")
    manual.write_text(before + manual_entry(day, request.form.get("description", ""), account, amount), encoding="utf-8")
    _, errors, _ = loader.load_file(str(ledger))
    if errors:
        manual.write_text(before, encoding="utf-8")
        return Response("Облік не прийняв цю витрату, її не збережено", status=400)
    month = f"{day.year}-{day.month:02d}"
    return Response(status=303, headers={"Location": f"./?who={who}&added={quote(str(amount))}#{month}"})


def report_app(environ, start_response):
    request = Request(environ)
    if request.path == "/add" and request.method == "POST":
        return add_expense(request)(environ, start_response)
    if request.path != "/":
        # Браузер сам питає /favicon.ico; без цього кожен такий запит перераховував би весь звіт.
        return Response("Не знайдено", status=404)(environ, start_response)
    return Response(report_page(), mimetype="text/html")(environ, start_response)


load_env()
report_page()  # прогрів: перший відвідувач не чекає на перерахунок
fava_app = create_app([info[0] for info in PEOPLE.values()])
application = require_password(
    DispatcherMiddleware(report_app, {"/fava": fava_app}),
    os.environ.get("TRACKER_USER", ""),
    os.environ.get("TRACKER_PASSWORD", ""),
)
