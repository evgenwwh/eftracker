"""Fava з обома обліками за паролем, для PythonAnywhere.

Логін і пароль беремо лише зі змінних середовища TRACKER_USER і TRACKER_PASSWORD.
На сервері їх кладемо у файл ~/.tracker.env (рядки KEY=VALUE), у репозиторії їх немає.
Без цих змінних трекер не показує жодних даних.
"""
import base64
import hmac
import os
from pathlib import Path

from fava.application import create_app

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = Path.home() / ".tracker.env"


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


load_env()
fava_app = create_app([ROOT / "ledger" / "marko.beancount", ROOT / "ledger" / "olia.beancount"])
application = require_password(
    fava_app, os.environ.get("TRACKER_USER", ""), os.environ.get("TRACKER_PASSWORD", "")
)
