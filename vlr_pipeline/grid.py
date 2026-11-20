"""Ingesta de la API de GRID (Open Access, Valorant) a JSON crudo en grid/raw/.

Dos pasos, los dos incrementales:

1. ``catalog``: Central Data ``allSeries`` (titleId 6, tipo ESPORTS) -> ``grid/raw/series_catalog.jsonl``, una
   serie por linea. La primera vez pide desde ``since``; despues solo lo que GRID modifico desde la ultima
   sincronizacion (filtro ``updatedAt``), asi entran las series nuevas y las corregidas.
2. ``states``: Series State de cada serie del catalogo -> ``grid/raw/series_state/<id>.json.gz`` (gzip: un
   Bo5 pesa 1.3 MB sin comprimir y el proyecto vive en OneDrive; DuckDB lee .json.gz directo). Se baja si
   falta, si no termino, si GRID la modifico despues de bajarla, o si se bajo hace menos de
   ``REFRESH_DAYS`` desde que empezo (GRID corrige series ya terminadas).

Esto es solo extraccion: no se transforma nada. El modelado (desarmar el JSON en serie/mapa/ronda/jugador)
es de dbt (``dbt/``, source ``grid``). Notas de la API en handoff/GRID_NOTES.md; lo importante para leer
estos archivos: GRID omite los campos null (no vienen en el JSON), hay que usar .get().

Los datos de GRID tienen licencia: grid/raw/ esta en .gitignore y no se suben a ningun lado.
"""

import gzip
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://api-op.grid.gg"
CENTRAL_URL = f"{BASE_URL}/central-data/graphql"
STATE_URL = f"{BASE_URL}/live-data-feed/series-state/graphql"

DEFAULT_GRID_DIR = os.path.join("grid", "raw")
CATALOG_FILE = "series_catalog.jsonl"
CATALOG_META_FILE = "catalog_meta.json"
STATE_DIR = "series_state"

VALORANT_TITLE_ID = "6"
DEFAULT_SINCE = "2026-01-01"  # lo que cubre vlr en csv/
REFRESH_DAYS = 3
# Margen al pedir "modificadas desde la ultima sync": una serie editada durante la corrida anterior no se pierde
CATALOG_OVERLAP = timedelta(hours=6)
PAGE_SIZE = 50
# Torneos de prueba de GRID (la serie 6, "GRID-TEST", VAL-1 vs VAL-2)
TEST_TOURNAMENT_PREFIXES = ("GRID-TEST",)

# Open Access: Central Data 20 req/min, Series State 180 req/min (6 por serie). Un poco por debajo del limite.
MIN_INTERVAL = {CENTRAL_URL: 60 / 18, STATE_URL: 60 / 150}
MAX_RETRIES = 4
# GRID avisa el rate limit como error GraphQL con HTTP 200 (no 429). El limite por serie es 6/min.
RATE_LIMIT_MESSAGE = "rate limit"
RATE_LIMIT_WAIT = 20


CATALOG_QUERY = """
query ($after: Cursor, $filter: SeriesFilter!) {
  allSeries(first: %d, after: $after, filter: $filter, orderBy: StartTimeScheduled, orderDirection: ASC) {
    totalCount
    pageInfo { endCursor hasNextPage }
    edges { node {
      id type startTimeScheduled updatedAt
      format { name nameShortened }
      externalLinks { dataProvider { name } externalEntity { id } }
      tournament {
        id name nameShortened startDate endDate
        parent { id name }
        externalLinks { dataProvider { name } externalEntity { id } }
      }
      teams {
        scoreAdvantage
        baseInfo {
          id name nameShortened
          externalLinks { dataProvider { name } externalEntity { id } }
        }
      }
    } }
  }
}
""" % PAGE_SIZE

# GameState.valid solo existe desde la version 3.50 del Series State ("Requested field is only available from
# version 3.50" en series de enero 2026, version 3.48): por eso no se pide. ``version`` queda en el JSON.
# Todo lo de Valorant que sirve de una serie terminada (ver GRID_NOTES.md). A nivel game, money / loadoutValue /
# alive / currentHealth son la foto del final del mapa; a nivel segment, alive / currentHealth son el final de
# cada ronda.
_DRAFT = "draftActions { id sequenceNumber type drafter { id type } draftable { id type name } }"
_OBJECTIVES = "objectives { type completionCount completedFirst }"
_WEAPON_KILLS = "weaponKills { weaponName count }"

STATE_QUERY = """
query ($id: ID!) {
  seriesState(id: $id) {
    id version format started finished forfeited valid startedAt duration updatedAt
    %(draft)s
    teams { id name score won }
    games {
      id sequenceNumber started finished forfeited startedAt duration
      map { id name }
      %(draft)s
      teams {
        id name
        ... on GameTeamStateValorant {
          side won score kills deaths headshots damageDealt damageTaken firstKill
          teamkills selfkills killAssistsGiven
          %(objectives)s
        }
        players {
          id name
          ... on GamePlayerStateValorant {
            character { id name }
            participationStatus
            kills deaths killAssistsGiven killAssistsReceived headshots firstKill
            teamkills selfkills damageDealt damageTaken teamdamageDealt
            ultimatePoints money loadoutValue netWorth alive currentHealth
            multikills { numberOfKills count }
            %(weapon_kills)s
            %(objectives)s
          }
        }
      }
      segments {
        id type sequenceNumber started finished startedAt duration
        teams {
          id name
          ... on SegmentTeamStateValorant {
            side won winType kills deaths headshots damageDealt damageTaken firstKill
            %(objectives)s
          }
          players {
            id name
            ... on SegmentPlayerStateValorant {
              participationStatus
              kills deaths killAssistsGiven killAssistsReceived headshots firstKill
              teamkills selfkills damageDealt damageTaken teamdamageDealt
              alive currentHealth currentArmor
              killAssistsReceivedFromPlayer { playerId killAssistsReceived }
              %(weapon_kills)s
              %(objectives)s
              damageDealtSources { source { name } damageAmount occurrenceCount }
              damageDealtTargets { target { name } damageAmount occurrenceCount }
            }
          }
        }
      }
    }
  }
}
""" % {"draft": _DRAFT, "objectives": _OBJECTIVES, "weapon_kills": _WEAPON_KILLS}


class GridError(RuntimeError):
    """Error de la API (HTTP o GraphQL) que no se arregla reintentando."""


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value):
    """ISO 8601 de GRID ('2026-11-01T17:53:07.857Z') a datetime con zona; None si falta."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def urllib_transport(url, payload, headers, timeout=60):
    """POST json; devuelve (status, body). Separado para poder reemplazarlo en los tests."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


class GridClient:
    """POST a GraphQL con rate limit por endpoint y reintentos en 429 / 5xx / errores de red."""

    def __init__(self, api_key, transport=urllib_transport, sleep=time.sleep, clock=time.monotonic):
        if not api_key:
            raise GridError("Falta GRID_API_KEY (entorno o .env.local)")
        self.api_key = api_key
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.last_call = {}

    def wait_turn(self, url):
        interval = MIN_INTERVAL.get(url, 0)
        last = self.last_call.get(url)
        if last is not None:
            remaining = interval - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self.last_call[url] = self.clock()

    def query(self, url, query, variables=None):
        """Devuelve ``data``. GRID omite los campos null, asi que data puede no traer la clave pedida."""
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key, "User-Agent": "vlr-pipeline"}
        payload = {"query": query, "variables": variables or {}}
        for attempt in range(1, MAX_RETRIES + 1):
            self.wait_turn(url)
            try:
                status, body = self.transport(url, payload, headers)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                status, body = None, str(exc)
            if status == 200:
                resp = json.loads(body)
                if resp.get("errors"):
                    messages = "; ".join(e.get("message", str(e)) for e in resp["errors"])
                    if RATE_LIMIT_MESSAGE in messages.lower() and attempt < MAX_RETRIES:
                        logger.warning("GRID rate limit (intento %d/%d), espero %ds", attempt, MAX_RETRIES,
                                       RATE_LIMIT_WAIT * attempt)
                        self.sleep(RATE_LIMIT_WAIT * attempt)
                        continue
                    raise GridError(f"GraphQL: {messages}")
                return resp.get("data") or {}
            if status in (401, 403):
                raise GridError(f"HTTP {status}: la key no tiene acceso ({body[:200]})")
            if status is not None and 400 <= status < 500 and status != 429:
                raise GridError(f"HTTP {status}: {body[:300]}")
            wait = min(60, 5 * 2 ** (attempt - 1))
            logger.warning("GRID %s (intento %d/%d), reintento en %ds", status or body, attempt, MAX_RETRIES, wait)
            self.sleep(wait)
        raise GridError(f"GRID no respondio despues de {MAX_RETRIES} intentos ({url})")


# --- catalogo -----------------------------------------------------------------------------------------------

def is_test_series(node):
    name = ((node.get("tournament") or {}).get("name")) or ""
    return name.startswith(TEST_TOURNAMENT_PREFIXES)


def read_jsonl(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def read_json(path, default=None):
    if not os.path.isfile(path):
        return default
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    tmp = path + ".tmp"
    if path.endswith(".gz"):
        # mtime=0: el mismo contenido da los mismos bytes (no cambia el archivo si GRID no cambio nada)
        with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    else:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def series_filter(since, updated_since=None):
    """Filtro de allSeries: Valorant, solo ESPORTS (sin scrims ni loopfeed), desde ``since``."""
    flt = {
        "titleId": VALORANT_TITLE_ID,
        "types": ["ESPORTS"],
        "startTimeScheduled": {"gte": since},
    }
    if updated_since:
        flt["updatedAt"] = {"gte": updated_since}
    return flt


def fetch_catalog_pages(client, flt):
    """Recorre todas las paginas de allSeries; devuelve los nodos."""
    nodes, after, total = [], None, None
    while True:
        data = client.query(CENTRAL_URL, CATALOG_QUERY, {"after": after, "filter": flt})
        page = data.get("allSeries") or {}
        total = page.get("totalCount", total)
        nodes.extend(edge["node"] for edge in page.get("edges") or [])
        info = page.get("pageInfo") or {}
        logger.info("catalogo GRID: %d/%s series", len(nodes), total)
        if not info.get("hasNextPage"):
            return nodes
        after = info.get("endCursor")


def sync_catalog(client, grid_dir=DEFAULT_GRID_DIR, since=DEFAULT_SINCE, full=False):
    """Actualiza series_catalog.jsonl. Devuelve (series en el catalogo, series nuevas o cambiadas)."""
    os.makedirs(grid_dir, exist_ok=True)
    catalog_path = os.path.join(grid_dir, CATALOG_FILE)
    meta_path = os.path.join(grid_dir, CATALOG_META_FILE)
    meta = read_json(meta_path, {}) or {}

    since_iso = f"{since}T00:00:00Z" if len(since) == 10 else since
    updated_since = None
    if not full and meta.get("since") == since_iso and meta.get("synced_at"):
        updated_since = iso(parse_time(meta["synced_at"]) - CATALOG_OVERLAP)
    started = utc_now()

    fetched = fetch_catalog_pages(client, series_filter(since_iso, updated_since))
    tests = [n["id"] for n in fetched if is_test_series(n)]
    if tests:
        logger.info("catalogo GRID: salteo %d series de prueba (%s)", len(tests), ", ".join(tests))

    by_id = {row["id"]: row for row in read_jsonl(catalog_path)} if updated_since else {}
    changed = 0
    for node in fetched:
        if is_test_series(node):
            by_id.pop(node["id"], None)
            continue
        if by_id.get(node["id"]) != node:
            changed += 1
        by_id[node["id"]] = node

    rows = sorted(by_id.values(), key=lambda n: (n.get("startTimeScheduled") or "", int(n["id"])))
    write_jsonl(catalog_path, rows)
    write_json(meta_path, {"since": since_iso, "synced_at": iso(started), "mode": "incremental" if updated_since
                           else "full", "series": len(rows)})
    logger.info("catalogo GRID: %d series (%d nuevas o cambiadas)", len(rows), changed)
    return len(rows), changed


# --- series state -------------------------------------------------------------------------------------------

def state_path(grid_dir, series_id):
    return os.path.join(grid_dir, STATE_DIR, f"{series_id}.json.gz")


def needs_state(node, saved, now):
    """Motivo para (re)bajar el Series State de una serie, o None si lo guardado sirve."""
    scheduled = parse_time(node.get("startTimeScheduled"))
    if scheduled and scheduled > now:
        return None  # todavia no se juega
    if saved is None:
        return "nueva"
    fetched_at = parse_time(saved.get("fetched_at"))
    state = saved.get("state") or {}
    if not state.get("finished"):
        return "sin terminar"
    updated = parse_time(node.get("updatedAt"))
    if updated and fetched_at and updated > fetched_at:
        return "modificada en GRID"
    if scheduled and fetched_at and fetched_at - scheduled < timedelta(days=REFRESH_DAYS):
        return f"bajada antes de {REFRESH_DAYS} dias"
    return None


def fetch_state(client, series_id):
    """Series State de una serie; None si GRID no tiene estado (serie nunca jugada: viene sin la clave)."""
    data = client.query(STATE_URL, STATE_QUERY, {"id": series_id})
    return data.get("seriesState")


def sync_states(client, grid_dir=DEFAULT_GRID_DIR, limit=None, series_ids=None, now=None):
    """Baja los Series State que hacen falta. Devuelve un dict con contadores por resultado."""
    now = now or utc_now()
    os.makedirs(os.path.join(grid_dir, STATE_DIR), exist_ok=True)
    catalog = read_jsonl(os.path.join(grid_dir, CATALOG_FILE))
    if series_ids:
        wanted = {str(s) for s in series_ids}
        catalog = [n for n in catalog if n["id"] in wanted]

    todo = []
    for node in catalog:
        reason = needs_state(node, read_json(state_path(grid_dir, node["id"])), now)
        if reason or series_ids:
            todo.append((node, reason or "pedida"))
    if limit:
        todo = todo[:limit]
    logger.info("series state GRID: %d por bajar de %d en el catalogo", len(todo), len(catalog))

    counts = {"ok": 0, "sin_estado": 0, "error": 0}
    for i, (node, reason) in enumerate(todo, 1):
        sid = node["id"]
        try:
            state = fetch_state(client, sid)
        except GridError as exc:
            counts["error"] += 1
            logger.warning("series state %s: %s", sid, exc)
            continue
        if state is None:
            counts["sin_estado"] += 1
            logger.info("series state %s: GRID no tiene estado (%s)", sid, reason)
            continue
        write_json(state_path(grid_dir, sid), {
            "series_id": sid,
            "fetched_at": iso(utc_now()),
            "state": state,
        })
        counts["ok"] += 1
        if i % 25 == 0 or i == len(todo):
            logger.info("series state GRID: %d/%d (%s)", i, len(todo), counts)
    return counts


def client_from_env():
    return GridClient(os.environ.get("GRID_API_KEY"))
