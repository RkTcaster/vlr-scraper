import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone

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

# "end_date" (YYYY-MM-DD, opcional) de un evento: deja de scrapearse END_DATE_GRACE_DAYS dias
# despues, aunque siga con "active": true. El margen cubre la corrida posterior a la final, los
# partidos que vlr cierra tarde y los 3 reintentos de un match con error (uno por corrida).
END_DATE_GRACE_DAYS = 3


def validate_slots(event, path=DEFAULT_EVENTS_FILE):
    """slots (plazas que da el evento) y relevant_teams (tricodes que las ocupan, a mano).

    Los dos son opcionales; relevant_teams pide slots y no puede tener mas equipos que plazas.
    Terminan en table_tournament_slots (tables.build_tournament_slots).
    """
    name = event.get("name", event.get("url"))
    slots = event.get("slots")
    teams = event.get("relevant_teams")
    if slots is not None and (isinstance(slots, bool) or not isinstance(slots, int) or slots < 1):
        raise ValueError(f"slots invalido en {path} para {name}: {slots!r} (entero >= 1)")
    if teams is None:
        return
    if slots is None:
        raise ValueError(f"relevant_teams sin slots en {path} para {name}")
    if not isinstance(teams, list) or not all(isinstance(team, str) and team.strip() for team in teams):
        raise ValueError(f"relevant_teams invalido en {path} para {name}: lista de tricodes")
    if len(teams) > slots:
        raise ValueError(f"{name} en {path}: {len(teams)} relevant_teams para {slots} slots")
    if len({team.strip().upper() for team in teams}) != len(teams):
        raise ValueError(f"relevant_teams repetidos en {path} para {name}: {teams}")


def parse_end_date(event, path=DEFAULT_EVENTS_FILE):
    """end_date del evento como date, o None si no tiene. Falla si no es YYYY-MM-DD."""
    value = event.get("end_date")
    if value is None:
        return None
    # fromisoformat solo sobre YYYY-MM-DD: en Python 3.11+ tambien acepta "20261116"
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:  # 2026-02-30
            pass
    raise ValueError(
        f"end_date invalido en {path} para {event.get('name', event.get('url'))}: {value!r} (YYYY-MM-DD)"
    )


def is_active(event, today=None):
    """active en events.json y, si tiene end_date, hoy (UTC) <= end_date + END_DATE_GRACE_DAYS.

    No reescribe events.json: "active" queda en true y el evento solo deja de devolverse.
    """
    if not event.get("active"):
        return False
    end_date = parse_end_date(event)
    if end_date is None:
        return True
    today = today or datetime.now(timezone.utc).date()
    return today <= end_date + timedelta(days=END_DATE_GRACE_DAYS)


def load_events(path=DEFAULT_EVENTS_FILE, only_active=True, today=None):
    """Lee events.json y devuelve la lista de eventos (dicts con name/url/active/format).

    Con only_active, solo los que is_active da por vigentes (active y end_date + margen sin vencer).
    """
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
        validate_slots(event, path)
        parse_end_date(event, path)
    if only_active:
        expired = [event for event in events if event.get("active") and not is_active(event, today)]
        for event in expired:
            logger.info(
                "%s: end_date %s + %d dias vencido, no se scrapea (sacar \"active\" o el end_date en %s)",
                event.get("name", event.get("url")), event["end_date"], END_DATE_GRACE_DAYS, path,
            )
        events = [event for event in events if is_active(event, today)]
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
