"""Las tablas construidas desde csv/ no tienen PKs duplicadas ni faltantes.

Usa la misma lista archivo -> tabla -> PK y el mismo chequeo que upload.py antes del upsert,
asi un duplicado se ve en CI y no recien cuando falla un bloque en Supabase.
"""

import os

import pytest

from vlr_pipeline.upload import FILES_TO_UPLOAD, read_rows, validate_rows

# tablas que pueden salir vacias: round_buy hasta correr backfill-logs sobre csv/
# (la tabla igual se testea con los fixtures en test_round_logs.py)
OPTIONAL_FILES = {"table_round_buy.csv"}


@pytest.mark.parametrize("file, table, pk, kind", FILES_TO_UPLOAD, ids=[entry[0] for entry in FILES_TO_UPLOAD])
def test_primary_key_unique(tables_dir, file, table, pk, kind):
    path = os.path.join(tables_dir, file)
    assert os.path.isfile(path), f"build_all no genero {file}"

    rows = read_rows(path)
    if not rows and file in OPTIONAL_FILES:
        pytest.skip(f"{file} vacio: csv/ todavia no tiene esos datos crudos")
    assert rows, f"{file} vacio"
    assert validate_rows(rows, pk, file) == []


@pytest.mark.parametrize("file, table, pk, kind", FILES_TO_UPLOAD, ids=[entry[0] for entry in FILES_TO_UPLOAD])
def test_primary_key_not_empty(tables_dir, file, table, pk, kind):
    rows = read_rows(os.path.join(tables_dir, file))
    pk_columns = [column.strip() for column in pk.split(",")]
    empty = [row for row in rows if any(row[column] == "" for column in pk_columns)]
    assert not empty, f"{file}: {len(empty)} filas con PK vacia, ej. {empty[:1]}"
