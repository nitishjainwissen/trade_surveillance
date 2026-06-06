import itertools
from datetime import datetime

_counter = itertools.count(1)


def next_alert_id() -> str:
    return f"ALT-{datetime.utcnow().year}-{next(_counter):04d}"
