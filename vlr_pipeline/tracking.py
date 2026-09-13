"""Log de matches scrapeados: csv/scrape_log.csv (dedup sin request + log de errores).

Una fila por match, con clave series_id (el numero de la url de vlr). La url completa no
sirve de clave: el slug cambia cuando un match "tbd-..." pasa a tener equipos, o si vlr
renombra un equipo, y vlr ignora el slug al servir la pagina.

Solo se registran matches que se intentaron procesar: los Upcoming/LIVE/TBD se filtran
antes (linkExtractor), asi que no quedan filas "fantasma".
"""

import csv
import glob
import logging
import os
import re
from datetime import datetime, timezone

import pandas as pd

from vlr_pipeline.save import normalize_filename

logger = logging.getLogger(__name__)

LOG_FILENAME = "scrape_log.csv"
LOG_COLUMNS = [
    "series_id",
    "url",
    "event",
    "tournament",
    "status",
    "error",
    "attempts",
    "has_performance",
    "has_economy",
    "first_seen",
    "last_attempt",
]
# ok: match completo. skipped: showmatch, no se vuelve a pedir. error: se reintenta.
DONE_STATUSES = {"ok", "skipped"}
MAX_ATTEMPTS = 3

# csv de datos donde un match deja filas (todos tienen columna source_url)
DATA_PREFIXES = ("round_detail", "player_stats", "player_performance", "team_economy", "draft")

# Los csv crudos se escriben con iso-8859-1 a partir de texto decodificado igual, asi que
# leer/escribir con latin-1 es un round trip exacto de los bytes.
RAW_ENCODING = "iso-8859-1"


def get_series_id(url):
    """series_id de una url de match de vlr, o None si no matchea"""
    result = re.search(r"vlr\.gg/(\d+)", str(url))
    return result.group(1) if result else None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log_path(folder):
    return os.path.join(folder, LOG_FILENAME)


def _read_source_urls(path):
    return pd.read_csv(path, usecols=["source_url"], encoding=RAW_ENCODING)["source_url"]


def bootstrap_log(folder="csv"):
    """Arma el log a partir de los csv existentes, para no re-scrapear lo que ya esta.

    - ok: cada source_url de csv/*/draft_*.csv (el draft se guarda ultimo).
    - error: cada url de csv/*/error_match_*.csv. Gana sobre ok: con el orden viejo de
      guardado el draft se escribia primero, asi que un match con error puede tener draft
      y estar incompleto. Al reintentarlo se purgan sus filas, asi que es idempotente.
    """
    rows = {}
    now = _now()

    for path in sorted(glob.glob(os.path.join(folder, "*", "draft_*.csv"))):
        tournament = os.path.basename(os.path.dirname(path))
        for url in _read_source_urls(path).dropna().unique():
            series_id = get_series_id(url)
            if series_id is None:
                continue
            rows[series_id] = {
                "series_id": series_id,
                "url": url,
                "event": "",
                "tournament": tournament,
                "status": "ok",
                "error": "",
                "attempts": 1,
                "has_performance": "",
                "has_economy": "",
                "first_seen": now,
                "last_attempt": now,
            }

    for path in sorted(glob.glob(os.path.join(folder, "*", "error_match_*.csv"))):
        tournament = os.path.basename(os.path.dirname(path))
        errors = pd.read_csv(path, encoding=RAW_ENCODING)
        for _, error_row in errors.iterrows():
            series_id = get_series_id(error_row["url"])
            if series_id is None:
                continue
            row = rows.get(series_id) or {
                "series_id": series_id,
                "url": error_row["url"],
                "tournament": tournament,
                "has_performance": "",
                "has_economy": "",
                "first_seen": now,
                "last_attempt": now,
            }
            row.update(
                event=error_row.get("event", ""),
                status="error",
                error=str(error_row.get("error", "")),
                attempts=1,
            )
            rows[series_id] = row

    log = pd.DataFrame(list(rows.values()), columns=LOG_COLUMNS)
    log = log.astype({column: str for column in LOG_COLUMNS if column != "attempts"})
    ok_count = int((log["status"] == "ok").sum())
    error_count = int((log["status"] == "error").sum())
    logger.info(f"scrape_log inicial: {ok_count} ok, {error_count} error (desde csv existentes)")
    return log


def load_log(folder="csv"):
    """Lee csv/scrape_log.csv; si no existe lo arma con bootstrap_log y lo guarda."""
    path = _log_path(folder)
    if not os.path.exists(path):
        log = bootstrap_log(folder)
        save_log(log, folder)
        return log

    log = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=RAW_ENCODING)
    for column in LOG_COLUMNS:
        if column not in log.columns:
            log[column] = ""
    log["attempts"] = pd.to_numeric(log["attempts"], errors="coerce").fillna(0).astype(int)
    return log[LOG_COLUMNS]


def save_log(log, folder="csv"):
    """Escribe el log entero via archivo temporal, para que un corte no lo deje a medias."""
    os.makedirs(folder, exist_ok=True)
    path = _log_path(folder)
    tmp_path = path + ".tmp"
    # los mensajes de error pueden traer caracteres fuera de latin-1
    log.to_csv(tmp_path, index=False, encoding=RAW_ENCODING, errors="replace")
    os.replace(tmp_path, path)


def should_skip(log, url):
    """True si el match ya esta (ok/skipped) o agoto los reintentos. Compara por series_id."""
    series_id = get_series_id(url)
    rows = log[log["series_id"] == series_id]
    if rows.empty:
        return False
    row = rows.iloc[0]
    if row["status"] in DONE_STATUSES:
        return True
    if int(row["attempts"]) >= MAX_ATTEMPTS:
        return True
    return False


def record(log, url, status, event="", error="", has_performance="", has_economy=""):
    """Upsert de la fila del match por series_id. Devuelve el log actualizado."""
    series_id = get_series_id(url)
    now = _now()
    values = {
        "url": url,
        "status": status,
        "error": error,
        "has_performance": has_performance,
        "has_economy": has_economy,
        "last_attempt": now,
    }
    if event:
        values["event"] = event
        values["tournament"] = normalize_filename(event)
    # todo como texto: el log se lee con dtype=str y pandas no deja meter bools ahi
    values = {column: "" if value is None else str(value) for column, value in values.items()}

    mask = log["series_id"] == series_id
    if mask.any():
        index = log.index[mask][0]
        for column, value in values.items():
            log.at[index, column] = value
        log.at[index, "attempts"] = int(log.at[index, "attempts"]) + 1
        return log

    row = {column: "" for column in LOG_COLUMNS}
    row.update(values, series_id=series_id, attempts=1, first_seen=now)
    return pd.concat([log, pd.DataFrame([row], columns=LOG_COLUMNS)], ignore_index=True)


def purge_match_rows(tournament, url, folder="csv"):
    """Borra las filas de un match (por series_id) de los csv de datos de su torneo.

    Se llama antes de procesar un match: si una corrida anterior fallo o se corto a medias,
    las filas parciales se van y el reproceso no duplica.

    Returns:
        int: cantidad de filas borradas
    """
    series_id = get_series_id(url)
    removed_total = 0

    for prefix in DATA_PREFIXES:
        path = os.path.join(folder, tournament, f"{prefix}_{tournament}.csv")
        if not os.path.exists(path):
            continue

        with open(path, newline="", encoding=RAW_ENCODING) as f:
            rows = list(csv.reader(f))
        if not rows or "source_url" not in rows[0]:
            continue

        url_index = rows[0].index("source_url")
        kept = [rows[0]] + [
            row for row in rows[1:]
            if len(row) <= url_index or get_series_id(row[url_index]) != series_id
        ]
        removed = len(rows) - len(kept)
        if removed == 0:
            continue

        with open(path, "w", newline="", encoding=RAW_ENCODING) as f:
            csv.writer(f).writerows(kept)
        removed_total += removed

    if removed_total:
        logger.info(f"purgadas {removed_total} filas parciales de {url}")
    return removed_total
