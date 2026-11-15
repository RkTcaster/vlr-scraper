"""Archivo de los csv de logs (round_buy_ / round_events_) en Supabase Storage.

Desde 2026-11-15 esos csv no van en git: son ~83% de csv/ y el round_buy_ del NA Open Qualifier
ya pasaba los 50 MB (GitHub rechaza archivos de mas de 100 MB). La copia completa vive en el
bucket privado BUCKET, un .csv.gz por archivo y version; en disco (local y en el runner de
Actions) siguen en csv/<torneo>/ como siempre, asi que scrape / process / upload no cambian.

- csv/logs_manifest.json (en git): que objeto del bucket es la version vigente de cada archivo.
- csv/.logs_synced.json (gitignored): que version bajo o subio esta maquina por ultima vez; es lo
  que distingue "el remoto es mas nuevo" (pull baja) de "hay cambios locales" (push sube).

Los objetos llevan el sha del contenido en el nombre y nunca se pisan: un push cortado a mitad
o dos pushes a la vez (local + Actions) no rompen la version a la que apunta el manifest. Las
versiones viejas se borran a mano con prune.

Invariante: has_logs=True en scrape_log.csv => las filas del match estan en la version del
archivo a la que apunta el manifest commiteado. Por eso Actions solo commitea csv/ si el push
del archivo salio bien.
"""

import gzip
import hashlib
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone

from vlr_pipeline.tracking import LOGS_PREFIXES

logger = logging.getLogger(__name__)

BUCKET = "vlr-logs"
MANIFEST_FILENAME = "logs_manifest.json"
SYNCED_FILENAME = ".logs_synced.json"


class ConflictError(RuntimeError):
    """El archivo cambio en local y en el remoto desde la ultima sincronizacion."""


# --- estado local -----------------------------------------------------------------------------

def _read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def load_manifest(csv_dir="csv"):
    return _read_json(os.path.join(csv_dir, MANIFEST_FILENAME))


def save_manifest(manifest, csv_dir="csv"):
    _write_json(os.path.join(csv_dir, MANIFEST_FILENAME), manifest)


def load_synced(csv_dir="csv"):
    return _read_json(os.path.join(csv_dir, SYNCED_FILENAME))


def save_synced(synced, csv_dir="csv"):
    _write_json(os.path.join(csv_dir, SYNCED_FILENAME), synced)


def is_logs_file(name):
    return name.endswith(".csv") and any(name.startswith(f"{prefix}_") for prefix in LOGS_PREFIXES)


def local_logs_files(csv_dir="csv"):
    """Claves '<torneo>/<archivo>.csv' de los csv de logs que hay en disco, ordenadas."""
    keys = []
    if not os.path.isdir(csv_dir):
        return keys
    for tournament in sorted(os.listdir(csv_dir)):
        folder = os.path.join(csv_dir, tournament)
        if not os.path.isdir(folder):
            continue
        keys += [f"{tournament}/{name}" for name in sorted(os.listdir(folder)) if is_logs_file(name)]
    return keys


def _path(csv_dir, key):
    return os.path.join(csv_dir, *key.split("/"))


def file_sha(path, synced_entry=None):
    """sha256 del archivo; reusa el de .logs_synced.json si tamano y mtime no cambiaron."""
    stat = os.stat(path)
    if synced_entry and synced_entry.get("size") == stat.st_size and synced_entry.get("mtime_ns") == stat.st_mtime_ns:
        return synced_entry["sha256"]
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _synced_entry(path, sha):
    stat = os.stat(path)
    return {"sha256": sha, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def object_name(key, sha):
    """Nombre del objeto en el bucket: ascii (Storage no acepta cualquier caracter) + sha.

    'vct_..._türkiye_qualifier/round_buy_..._türkiye_qualifier.csv' ->
    'vct_..._turkiye_qualifier/round_buy_..._turkiye_qualifier.<sha12>.csv.gz'
    """
    ascii_key = unicodedata.normalize("NFKD", key).encode("ascii", "ignore").decode("ascii")
    ascii_key = re.sub(r"[^A-Za-z0-9_./-]", "_", ascii_key)
    return f"{ascii_key[:-len('.csv')]}.{sha[:12]}.csv.gz"


# --- estado de cada archivo -------------------------------------------------------------------

def file_states(csv_dir="csv"):
    """Compara disco, manifest y ultima sincronizacion de cada archivo de logs.

    Returns:
        dict: clave -> (estado, sha_local). Estados: ok, download (remoto mas nuevo o falta en
        disco), upload (cambio local o archivo nuevo), conflict (cambiaron los dos).
    """
    manifest = load_manifest(csv_dir)
    synced = load_synced(csv_dir)
    states = {}
    for key in sorted(set(manifest) | set(local_logs_files(csv_dir))):
        path = _path(csv_dir, key)
        remote = manifest.get(key, {}).get("sha256")
        last = synced.get(key, {}).get("sha256")
        local = file_sha(path, synced.get(key)) if os.path.exists(path) else None

        if local == remote:
            state = "ok"
        elif local is None:
            state = "download"
        elif remote is None or remote == last:
            state = "upload"
        elif local == last:
            state = "download"
        else:
            # sin sincronizacion previa (otra maquina) o cambiaron los dos lados
            state = "conflict"
        states[key] = (state, local)
    return states


def pending_summary(csv_dir="csv"):
    """Cantidad de archivos por estado distinto de ok (sin red)."""
    summary = {}
    for state, _ in file_states(csv_dir).values():
        if state != "ok":
            summary[state] = summary.get(state, 0) + 1
    return summary


def warn_if_out_of_sync(csv_dir="csv"):
    """Warning si csv/ no tiene la version vigente de los logs (process daria tablas incompletas)."""
    if not load_manifest(csv_dir):
        return
    summary = pending_summary(csv_dir)
    if summary.get("download") or summary.get("conflict"):
        logger.warning(
            "csv de logs desactualizados respecto de %s (%s): correr 'python -m vlr_pipeline logs pull'",
            MANIFEST_FILENAME, summary,
        )


# --- operaciones contra el bucket -------------------------------------------------------------

def _bucket(client):
    return client.storage.from_(BUCKET)


def ensure_bucket(client):
    """Crea el bucket privado si no existe."""
    if any(getattr(b, "id", None) == BUCKET or getattr(b, "name", None) == BUCKET
           for b in client.storage.list_buckets()):
        return False
    client.storage.create_bucket(BUCKET, options={"public": False})
    logger.info("bucket %s creado (privado)", BUCKET)
    return True


def pull(client, csv_dir="csv", force=False):
    """Baja la version vigente de cada archivo que este desactualizado en disco.

    Un archivo en conflicto no se toca (salvo force, que pisa el local) y al final se levanta
    ConflictError. Los que tienen cambios locales sin subir tampoco se tocan.

    Returns:
        int: archivos bajados
    """
    manifest = load_manifest(csv_dir)
    synced = load_synced(csv_dir)
    downloaded = 0
    conflicts = []

    for key, (state, local) in file_states(csv_dir).items():
        if key not in manifest:
            continue
        if state == "ok":
            # sin .logs_synced.json (runner nuevo) igual queda registrado
            synced[key] = _synced_entry(_path(csv_dir, key), local)
            continue
        if state == "upload" or (state == "conflict" and not force):
            if state == "conflict":
                conflicts.append(key)
            continue

        entry = manifest[key]
        data = gzip.decompress(_bucket(client).download(entry["object"]))
        sha = hashlib.sha256(data).hexdigest()
        if sha != entry["sha256"]:
            raise RuntimeError(f"{entry['object']}: sha {sha[:12]} no coincide con el manifest")

        path = _path(csv_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        synced[key] = _synced_entry(path, sha)
        save_synced(synced, csv_dir)
        downloaded += 1
        logger.info("logs pull: %s (%.1f MB)", key, len(data) / 2**20)

    save_synced(synced, csv_dir)
    logger.info("logs pull: %d archivos bajados", downloaded)
    if conflicts:
        raise ConflictError(
            f"{len(conflicts)} archivos cambiaron en local y en el remoto: {conflicts}. "
            "Revisar a mano; 'logs pull --force' pisa el local, 'logs push --force' pisa el remoto"
        )
    return downloaded


def push(client, csv_dir="csv", force=False):
    """Sube los archivos con cambios locales y actualiza el manifest.

    El manifest se actualiza archivo por archivo y solo despues de que el objeto subio: si un
    upload falla, lo ya subido queda registrado y el resto se reintenta en el proximo push.

    Returns:
        int: archivos subidos
    """
    manifest = load_manifest(csv_dir)
    synced = load_synced(csv_dir)
    uploaded = 0
    conflicts = []

    for key, (state, local) in file_states(csv_dir).items():
        if state == "conflict" and not force:
            conflicts.append(key)
            continue
        if state not in ("upload", "conflict"):
            continue

        path = _path(csv_dir, key)
        with open(path, "rb") as f:
            data = f.read()
        name = object_name(key, local)
        _bucket(client).upload(
            name, gzip.compress(data, 6),
            file_options={"content-type": "application/gzip", "upsert": "true"},
        )
        manifest[key] = {
            "sha256": local,
            "object": name,
            "bytes": len(data),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        synced[key] = _synced_entry(path, local)
        save_manifest(manifest, csv_dir)
        save_synced(synced, csv_dir)
        uploaded += 1
        logger.info("logs push: %s (%.1f MB)", key, len(data) / 2**20)

    logger.info("logs push: %d archivos subidos", uploaded)
    if conflicts:
        raise ConflictError(
            f"{len(conflicts)} archivos cambiaron en local y en el remoto: {conflicts}. "
            "Hacer 'git pull' (puede traer un manifest nuevo) y revisar; 'logs push --force' pisa el remoto"
        )
    return uploaded


def prune(client, csv_dir="csv", keep=3, dry_run=False):
    """Borra versiones viejas: por archivo deja la vigente y las keep-1 mas recientes.

    Returns:
        list: objetos borrados (o a borrar, con dry_run)
    """
    manifest = load_manifest(csv_dir)
    current = {entry["object"] for entry in manifest.values()}
    to_remove = []
    for folder in sorted({entry["object"].rsplit("/", 1)[0] for entry in manifest.values()}):
        objects = _bucket(client).list(folder, {"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}})
        by_stem = {}
        for obj in objects:
            name = f"{folder}/{obj['name']}"
            stem = re.sub(r"\.[0-9a-f]{12}\.csv\.gz$", "", name)
            by_stem.setdefault(stem, []).append(name)
        for names in by_stem.values():
            others = [name for name in names if name not in current]
            to_remove += others[max(keep - 1, 0):]
    if to_remove and not dry_run:
        for start in range(0, len(to_remove), 100):
            _bucket(client).remove(to_remove[start:start + 100])
    logger.info("logs prune: %d objetos %s", len(to_remove), "a borrar (dry-run)" if dry_run else "borrados")
    return to_remove
