import json

DEFAULT_EVENTS_FILE = "events.json"
DEFAULT_CSV_DIR = "csv"
DEFAULT_TABLES_DIR = "tables"
# El driver original del notebook escribia los csv crudos con iso-8859-1.
DEFAULT_SCRAPE_ENCODING = "iso-8859-1"
DEFAULT_BUCKET = "tables"


def load_events(path=DEFAULT_EVENTS_FILE, only_active=True):
    """Lee events.json y devuelve la lista de eventos (dicts con name/url/active)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    if only_active:
        events = [event for event in events if event.get("active")]
    return events
