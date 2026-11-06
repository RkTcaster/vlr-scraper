import json
import logging
import os

logger = logging.getLogger(__name__)

# credenciales locales (gitignoreado). VLR_ENV_FILE lo pisa; vacio = no leer nada (lo usan los tests)
DEFAULT_ENV_FILE = ".env.local"
# nombre que usa el pipeline -> nombres alternativos aceptados en el archivo (los de rktdata / Next.js).
# La anon key NO sirve: el upsert necesita la service_role.
ENV_ALIASES = {
    "SUPABASE_URL": ("NEXT_PUBLIC_SUPABASE_URL",),
    "SUPABASE_SERVICE_KEY": ("SUPABASE_SERVICE_ROLE_KEY",),
}

DEFAULT_EVENTS_FILE = "events.json"
DEFAULT_CSV_DIR = "csv"
DEFAULT_TABLES_DIR = "tables"
# El driver original del notebook escribia los csv crudos con iso-8859-1.
DEFAULT_SCRAPE_ENCODING = "iso-8859-1"

# "format" de un evento en events.json. full: torneo con picks/bans; reduced: qualifiers y
# similares donde vlr no carga el draft (los bans y el mapa decider). Sin "format" = full.
MATCH_FORMATS = ("full", "reduced")
DEFAULT_MATCH_FORMAT = "full"


def load_events(path=DEFAULT_EVENTS_FILE, only_active=True):
    """Lee events.json y devuelve la lista de eventos (dicts con name/url/active/format)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    events = data.get("events", [])
    for event in events:
        event.setdefault("format", DEFAULT_MATCH_FORMAT)
        if event["format"] not in MATCH_FORMATS:
            raise ValueError(
                f"format invalido en {path} para {event.get('name', event.get('url'))}: "
                f"{event['format']!r} (opciones: {', '.join(MATCH_FORMATS)})"
            )
    if only_active:
        events = [event for event in events if event.get("active")]
    return events


def parse_env_file(path):
    """KEY=VALUE por linea; ignora vacias y comentarios, acepta "export " y comillas."""
    values = {}
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def load_env_file(path=None):
    """Carga credenciales de .env.local en os.environ sin pisar lo que ya este definido.

    Asi en Actions mandan los secrets y en local alcanza con el archivo. Los nombres de
    ENV_ALIASES se copian al nombre que usa el pipeline. Solo se loguean nombres, nunca valores.

    Returns:
        list: variables que se agregaron al entorno
    """
    if path is None:
        path = os.environ.get("VLR_ENV_FILE", DEFAULT_ENV_FILE)
    if not path or not os.path.isfile(path):
        return []

    values = parse_env_file(path)
    for name, aliases in ENV_ALIASES.items():
        if name not in values:
            for alias in aliases:
                if values.get(alias):
                    values[name] = values[alias]
                    break

    added = []
    for key, value in values.items():
        if value and not os.environ.get(key):
            os.environ[key] = value
            added.append(key)
    if added:
        logger.info("variables cargadas desde %s: %s", path, ", ".join(sorted(added)))
    return added
