"""Merge driver de git para los csv de csv/ (los commitea el bot todos los dias y tambien se tocan en local).

git hace merges por linea, y dos lados que agregan o reescriben filas del mismo csv chocan aunque no
se pisen (p.ej. el bot suma series nuevas y en local se agrega una columna a scrape_log). Este driver
hace un merge de 3 vias **por serie**:

- Las filas se agrupan por serie: columna `series_id` (scrape_log), o el id de `source_url` / `url`
  (csv crudos por torneo, error_match). Un archivo sin esas columnas (upload_log) se une fila a fila.
- Por cada serie: si solo un lado la cambio respecto de la base, gana ese lado; si los dos la cambiaron
  igual, da lo mismo; si la cambiaron distinto, gana **ours** (lo local: un re-scrape a mano es
  deliberado) y se avisa por stderr.
- Los cambios se comparan solo en las columnas de la base, asi una columna nueva de un lado (p.ej.
  `match_format`) no cuenta como cambio de todas las filas. El header final es el de ours mas las
  columnas que solo tenga theirs; lo que falte queda vacio.

Los bytes se leen como latin-1 (pasan intactos: los csv mezclan utf-8 e iso-8859-1) y se respeta el fin
de linea de ours.

Instalacion (una vez por clon; la asociacion a los archivos esta en .gitattributes):
    git config merge.vlr-csv.name "merge de csv/ por serie"
    git config merge.vlr-csv.driver "python scripts/merge_csv.py %O %A %B %P"

Tambien sirve para resolver a mano un merge que ya quedo en conflicto:
    python scripts/merge_csv.py --resolve [archivo ...]   # sin archivos: todos los csv en conflicto
"""

import csv
import io
import re
import subprocess
import sys

ENCODING = "iso-8859-1"
SERIES_RE = re.compile(r"vlr\.gg/(\d+)")


def read_table(data):
    """bytes -> (header, rows como dicts, fin de linea). Vacio -> ([], [], None)."""
    text = data.decode(ENCODING)
    if not text.strip():
        return [], [], None
    newline = "\r\n" if "\r\n" in text.split("\n", 1)[0] + "\n" else "\n"
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = list(reader)
    header, body = rows[0], rows[1:]
    return header, [dict(zip(header, row)) for row in body if row], newline


def key_function(header):
    if "series_id" in header:
        return lambda row: row.get("series_id", "")
    for column in ("source_url", "url"):
        if column in header:
            def key(row, column=column):
                match = SERIES_RE.search(row.get(column, ""))
                return match.group(1) if match else row.get(column, "")
            return key
    return None


def group(rows, key):
    groups = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    return groups


def project(rows, columns):
    return [tuple(row.get(column, "") for column in columns) for row in rows or []]


def fill_new_columns(chosen, donor, columns):
    """Copia a las filas elegidas las columnas que solo tiene el otro lado (misma serie, mismo orden)."""
    if not donor:
        return chosen
    out = []
    for i, row in enumerate(chosen):
        row = dict(row)
        source = donor[i] if i < len(donor) else donor[-1]
        for column in columns:
            if not row.get(column):
                row[column] = source.get(column, "")
        out.append(row)
    return out


def merge(base_bytes, ours_bytes, theirs_bytes, name="csv"):
    """Merge de 3 vias. Returns: (bytes, lista de avisos)."""
    base_header, base_rows, _ = read_table(base_bytes)
    ours_header, ours_rows, newline = read_table(ours_bytes)
    theirs_header, theirs_rows, theirs_newline = read_table(theirs_bytes)
    newline = newline or theirs_newline or "\r\n"
    header = ours_header + [c for c in theirs_header if c not in ours_header]
    if not header:
        return ours_bytes, []
    compare = base_header or [c for c in ours_header if c in theirs_header]
    only_ours = [c for c in ours_header if c not in theirs_header]
    only_theirs = [c for c in theirs_header if c not in ours_header]
    warnings = []

    key = key_function(header)
    if key is None:
        # sin serie (upload_log, que solo crece): union fila a fila, sin repetir
        seen, merged = set(), []
        for row in ours_rows + theirs_rows:
            ident = tuple(row.get(c, "") for c in header)
            if ident not in seen:
                seen.add(ident)
                merged.append(row)
        if header and header[0].endswith("_at"):
            merged.sort(key=lambda row: row.get(header[0], ""))
    else:
        base_groups = group(base_rows, key)
        ours_groups = group(ours_rows, key)
        theirs_groups = group(theirs_rows, key)
        order = list(ours_groups) + [k for k in theirs_groups if k not in ours_groups]
        merged = []
        for k in order:
            base, ours, theirs = base_groups.get(k), ours_groups.get(k), theirs_groups.get(k)
            ours_changed = project(ours, compare) != project(base, compare)
            theirs_changed = project(theirs, compare) != project(base, compare)
            if theirs_changed and not ours_changed:
                rows = fill_new_columns(theirs or [], ours, only_ours)
            else:
                if ours_changed and theirs_changed and project(ours, compare) != project(theirs, compare):
                    warnings.append(f"{name}: serie {k} cambio en los dos lados; queda la version local")
                rows = fill_new_columns(ours or [], theirs, only_theirs)
            merged.extend(rows)

    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator=newline)
    writer.writerow(header)
    for row in merged:
        writer.writerow([row.get(c, "") for c in header])
    return out.getvalue().encode(ENCODING), warnings


def git_show(stage, path):
    result = subprocess.run(["git", "show", f":{stage}:{path}"], capture_output=True)
    return result.stdout if result.returncode == 0 else b""


def resolve(paths):
    if not paths:
        listed = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "--name-only", "--diff-filter=U"],
            capture_output=True, check=True,
        ).stdout.decode("utf-8")
        paths = [p for p in listed.splitlines() if p.startswith("csv/") and p.endswith(".csv")]
    for path in paths:
        data, warnings = merge(git_show(1, path), git_show(2, path), git_show(3, path), path)
        with open(path, "wb") as f:
            f.write(data)
        for warning in warnings:
            print(warning, file=sys.stderr)
        print(f"resuelto: {path}")
    return 0


def main(argv):
    if argv and argv[0] == "--resolve":
        return resolve(argv[1:])
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    base_path, ours_path, theirs_path = argv[:3]
    name = argv[3] if len(argv) > 3 else ours_path
    with open(base_path, "rb") as f:
        base = f.read()
    with open(ours_path, "rb") as f:
        ours = f.read()
    with open(theirs_path, "rb") as f:
        theirs = f.read()
    try:
        data, warnings = merge(base, ours, theirs, name)
    except Exception as exc:  # que git lo deje en conflicto en vez de escribir algo roto
        print(f"merge_csv: no pude mergear {name}: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(warning, file=sys.stderr)
    with open(ours_path, "wb") as f:
        f.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
