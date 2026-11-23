"""upload.py con un cliente de Supabase falso: upsert por bloques, errores y upload_log.

Sin red: FakeClient guarda lo que se le manda y puede fallar en la tabla que se le pida.
"""

import csv

import pytest

from vlr_pipeline import upload
from vlr_pipeline.cli import main

ORBS_HEADER = ["team_map_round_id", "team_id_vlr", "series_id", "map_id", "map", "round", "team", "side", "orbs",
               "tour_id"]


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.rows = None

    def upsert(self, rows, on_conflict=None, returning=None):
        self.rows = rows
        self.on_conflict = on_conflict
        return self

    def execute(self):
        if self.table in self.client.fail_tables:
            raise RuntimeError(f"fallo {self.table}")
        self.client.upserts.append((self.table, self.on_conflict, self.rows))
        return self


class FakeClient:
    def __init__(self, fail_tables=()):
        self.fail_tables = set(fail_tables)
        self.upserts = []

    def table(self, name):
        return FakeQuery(self, name)


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def orbs_rows(n_rounds):
    rows = []
    for rnd in range(1, n_rounds + 1):
        for team_id, tag in (("1", "AAA"), ("2", "BBB")):
            rows.append([f"AAA-BBB-100-Bind-{rnd}", team_id, "100", "100-Bind", "Bind", rnd, tag, "atk", 1, "t1"])
    return rows


def read_log(log_dir):
    with open(log_dir / upload.UPLOAD_LOG_FILENAME, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_grid_upload_sends_all_rows_in_chunks(tmp_path):
    write_csv(tmp_path / "exports" / "table_team_orbs.csv", ORBS_HEADER, orbs_rows(5))
    client = FakeClient()

    errors = upload.run_grid_upload(client, exports_dir=str(tmp_path / "exports"), chunk_size=4, log_dir=tmp_path)

    assert errors == 0
    assert [len(rows) for _, _, rows in client.upserts] == [4, 4, 2]
    assert {(table, pk) for table, pk, _ in client.upserts} == {("team_orbs", "team_map_round_id, team_id_vlr")}
    [entry] = read_log(tmp_path)
    assert (entry["mode"], entry["table"], entry["rows"], entry["series"], entry["status"]) == (
        "grid", "team_orbs", "10", "1", "ok")


def test_grid_upload_missing_export_is_an_error(tmp_path):
    client = FakeClient()

    errors = upload.run_grid_upload(client, exports_dir=str(tmp_path / "no_existe"), log_dir=tmp_path)

    assert errors == 1
    assert client.upserts == []
    assert read_log(tmp_path)[0]["status"] == "missing"


def test_grid_upload_duplicated_pk_uploads_nothing(tmp_path):
    rows = orbs_rows(2)
    write_csv(tmp_path / "exports" / "table_team_orbs.csv", ORBS_HEADER, rows + rows[:1])
    client = FakeClient()

    errors = upload.run_grid_upload(client, exports_dir=str(tmp_path / "exports"), log_dir=tmp_path)

    assert errors == 1
    assert client.upserts == []
    assert read_log(tmp_path)[0]["status"] == "invalid"


def test_grid_upload_failed_chunk_is_logged(tmp_path):
    write_csv(tmp_path / "exports" / "table_team_orbs.csv", ORBS_HEADER, orbs_rows(3))
    client = FakeClient(fail_tables={"team_orbs"})

    errors = upload.run_grid_upload(client, exports_dir=str(tmp_path / "exports"), chunk_size=4, log_dir=tmp_path)

    assert errors == 2  # dos bloques (4 + 2 filas), los dos fallan
    [entry] = read_log(tmp_path)
    assert (entry["status"], entry["failed_rows"]) == ("error", "6")
    assert "fallo team_orbs" in entry["error"]


def test_grid_upload_dry_run_needs_no_client_and_writes_no_log(tmp_path):
    write_csv(tmp_path / "exports" / "table_team_orbs.csv", ORBS_HEADER, orbs_rows(1))

    errors = upload.run_grid_upload(None, exports_dir=str(tmp_path / "exports"), dry_run=True, log_dir=tmp_path)

    assert errors == 0
    assert not (tmp_path / upload.UPLOAD_LOG_FILENAME).exists()


def test_grid_exports_are_not_in_the_daily_upload():
    # el cron (upload / all) no tiene grid/raw: los exports de GRID no pueden estar en FILES_TO_UPLOAD
    daily = {table for _, table, _, _ in upload.FILES_TO_UPLOAD}
    assert daily.isdisjoint({table for _, table, _ in upload.GRID_FILES_TO_UPLOAD})


def test_cli_upload_grid_dry_run(tmp_path):
    write_csv(tmp_path / "table_team_orbs.csv", ORBS_HEADER, orbs_rows(1))
    assert main(["upload-grid", "--exports-dir", str(tmp_path), "--csv-dir", str(tmp_path), "--dry-run"]) == 0
    assert main(["upload-grid", "--exports-dir", str(tmp_path / "vacio"), "--csv-dir", str(tmp_path),
                 "--dry-run"]) == 1


@pytest.fixture
def one_table(monkeypatch):
    """FILES_TO_UPLOAD reducido a una tabla de hechos y match_id, para probar run_upload en full."""
    monkeypatch.setattr(upload, "FILES_TO_UPLOAD", [
        ("table_round_info.csv", "round_info", "team_map_round_id", upload.FACT),
        ("table_match_id.csv", "match_id", "series_id", upload.MARKER),
    ])


def test_daily_upload_failed_fact_chunk_keeps_series_out_of_match_id(tmp_path, one_table):
    # _upsert_rows se comparte con run_upload: un bloque de hechos fallido no marca su serie en match_id
    write_csv(tmp_path / "table_round_info.csv", ["team_map_round_id", "series_id"], [["r1", "100"], ["r2", "200"]])
    write_csv(tmp_path / "table_match_id.csv", ["series_id"], [["100"], ["200"]])
    client = FakeClient(fail_tables={"round_info"})

    errors = upload.run_upload(client, tables_dir=str(tmp_path), log_dir=tmp_path, full=True, csv_dir=tmp_path)

    assert errors == 1
    assert [table for table, _, _ in client.upserts] == []  # round_info fallo y match_id quedo sin filas
    log = {row["table"]: row for row in read_log(tmp_path)}
    assert (log["round_info"]["status"], log["round_info"]["failed_rows"]) == ("error", "2")
    assert log["match_id"]["rows"] == "0"


def test_daily_upload_ok(tmp_path, one_table):
    write_csv(tmp_path / "table_round_info.csv", ["team_map_round_id", "series_id"], [["r1", "100"]])
    write_csv(tmp_path / "table_match_id.csv", ["series_id"], [["100"]])
    client = FakeClient()

    assert upload.run_upload(client, tables_dir=str(tmp_path), log_dir=tmp_path, full=True, csv_dir=tmp_path) == 0
    assert [table for table, _, _ in client.upserts] == ["round_info", "match_id"]
