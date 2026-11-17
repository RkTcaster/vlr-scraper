"""Une la carpeta de un torneo dentro de otra (vlr renombro el evento a mitad de camino).

    python scripts/merge_tournament.py <carpeta_vieja> <carpeta_nueva> [--csv-dir csv] [--dry-run]

Caso 2026-11-16: "VCT 2027: EMEA Kickoff - Europe Qualifier" paso a llamarse "... Europe Open
Qualifier", asi que el Qualifier #2 cayo en otra carpeta (= otro tour_id) que el #1.

Que hace, sin requests a vlr ni a Supabase:
  - cada csv de la carpeta vieja se antepone al de la nueva (mismo prefijo), con la columna `event`
    reescrita al nombre nuevo. Todo en bytes: no se decodifica nada (ver "Encoding" en CLAUDE.md).
  - scrape_log.csv: `event` y `tournament` de esas series pasan al nombre nuevo.
  - logs_manifest.json / .logs_synced.json: saca las entradas de la carpeta vieja (si quedan,
    `logs pull` vuelve a bajar los archivos). Los objetos del bucket no se tocan.
  - borra la carpeta vieja.

Despues: `process`, `logs push`, el sql de limpieza del tour_id viejo en Supabase y `upload`.
"""

import argparse
import json
import os
import re
import sys

LOG_FILE = "scrape_log.csv"
JSON_FILES = ("logs_manifest.json", ".logs_synced.json")


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_bytes(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def split_header(data):
    """(header con su fin de linea, resto)."""
    end = data.index(b"\n") + 1
    return data[:end], data[end:]


def event_name(csv_dir, folder):
    """Nombre del evento de una carpeta, tal como esta en scrape_log (bytes)."""
    header, body = split_header(read_bytes(os.path.join(csv_dir, LOG_FILE)))
    columns = header.strip().split(b",")
    event_at, tournament_at = columns.index(b"event"), columns.index(b"tournament")
    if tournament_at != event_at + 1:
        raise SystemExit("scrape_log: se esperaba `tournament` justo despues de `event`")
    names = set()
    for line in body.splitlines():
        marker = b"," + folder.encode("iso-8859-1") + b","
        if marker in line:
            names.add(line[: line.index(marker)].split(b",")[-1])
    if len(names) != 1:
        raise SystemExit(f"scrape_log: {folder} tiene {len(names)} nombres de evento: {names}")
    return names.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("old")
    parser.add_argument("new")
    parser.add_argument("--csv-dir", default="csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    old_dir = os.path.join(args.csv_dir, args.old)
    new_dir = os.path.join(args.csv_dir, args.new)
    for folder in (old_dir, new_dir):
        if not os.path.isdir(folder):
            raise SystemExit(f"no existe {folder}")

    old_event, new_event = event_name(args.csv_dir, args.old), event_name(args.csv_dir, args.new)
    print(f"evento: {old_event.decode('iso-8859-1')!r} -> {new_event.decode('iso-8859-1')!r}")
    old_cell, new_cell = b"," + old_event + b",", b"," + new_event + b","
    old_cell_re = re.compile(b"," + re.escape(old_event) + rb"(?=,|\r?\n)")

    # 1. csv: viejo (con el event nuevo) + nuevo
    merged = {}
    for name in sorted(os.listdir(old_dir)):
        if not name.endswith(f"_{args.old}.csv"):
            raise SystemExit(f"archivo inesperado en {old_dir}: {name}")
        prefix = name[: -len(f"{args.old}.csv")]
        target = os.path.join(new_dir, f"{prefix}{args.new}.csv")
        header, body = split_header(read_bytes(os.path.join(old_dir, name)))
        rows = body.count(b"\n")
        # la celda puede ser la ultima de la fila (team_economy): termina en coma o en fin de linea
        renamed, replaced = old_cell_re.subn(b"," + new_event, body)
        if replaced != rows:
            raise SystemExit(f"{name}: {rows} filas pero {replaced} celdas con el evento {old_event!r}")
        if body and not body.endswith(b"\n"):
            raise SystemExit(f"{name}: no termina en fin de linea")
        if os.path.exists(target):
            new_header, new_body = split_header(read_bytes(target))
            if new_header != header:
                raise SystemExit(f"{name}: el header no coincide con {target}")
            renamed += new_body
        merged[target] = header + renamed
        print(f"  {prefix:22} {rows:7} filas viejas -> {renamed.count(chr(10).encode()):7} en total")

    # 2. scrape_log
    log_path = os.path.join(args.csv_dir, LOG_FILE)
    log = read_bytes(log_path)
    old_pair = old_cell + args.old.encode("iso-8859-1") + b","
    new_pair = new_cell + args.new.encode("iso-8859-1") + b","
    print(f"scrape_log: {log.count(old_pair)} series")
    new_log = log.replace(old_pair, new_pair)

    # 3. manifest / synced
    new_json = {}
    for name in JSON_FILES:
        path = os.path.join(args.csv_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        dropped = [key for key in data if key.startswith(args.old + "/")]
        print(f"{name}: saco {len(dropped)} entradas")
        new_json[path] = {key: value for key, value in data.items() if key not in dropped}

    if args.dry_run:
        print("dry-run: no se escribio nada")
        return 0

    for path, data in merged.items():
        write_bytes(path, data)
    write_bytes(log_path, new_log)
    for path, data in new_json.items():
        # mismo formato que logs_archive._write_json
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")
    for name in os.listdir(old_dir):
        os.remove(os.path.join(old_dir, name))
    os.rmdir(old_dir)
    print(f"listo: {old_dir} unida en {new_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
