"""Трекер для PythonAnywhere: сторінка звіту Марка й Олі на /, Fava на /fava, усе за паролем.

Логін і пароль беремо лише зі змінних середовища TRACKER_USER і TRACKER_PASSWORD.
На сервері їх кладемо у файл ~/.tracker.env (рядки KEY=VALUE), у репозиторії їх немає.
Без цих змінних трекер не показує жодних даних.
"""
import base64
import hmac
import os
from pathlib import Path

from fava.application import create_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Request, Response

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = Path.home() / ".tracker.env"
# хто: (підпис, облік, адреса облікової книги у Fava)
PEOPLE = {
    "marko": ("Марко", ROOT / "ledger" / "marko.beancount", "фінанси-марка"),
    "olia": ("Оля", ROOT / "ledger" / "olia.beancount", "фінанси-олі"),
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


def report_app(environ, start_response):
    from tracker.report import render

    who = Request(environ).args.get("who", "marko")
    if who not in PEOPLE:
        who = "marko"
    name, ledger, slug = PEOPLE[who]
    links = "".join(
        f'<a href="?who={key}"{' aria-current="page"' if key == who else ''}>{label}</a>'
        for key, (label, _, _) in PEOPLE.items()
    )
    nav = (f'<nav class="people">{links}'
           f'<a class="add" href="fava/{slug}/journal/">Додати витрату</a></nav>')
    title = "Фінанси Марка" if who == "marko" else "Фінанси Олі"
    return Response(render(ledger, title, nav), mimetype="text/html")(environ, start_response)


load_env()
fava_app = create_app([info[1] for info in PEOPLE.values()])
application = require_password(
    DispatcherMiddleware(report_app, {"/fava": fava_app}),
    os.environ.get("TRACKER_USER", ""),
    os.environ.get("TRACKER_PASSWORD", ""),
)
