"""scripts/merge_csv.py: merge de 3 vias por serie para los csv de csv/."""

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "merge_csv.py")
spec = importlib.util.spec_from_file_location("merge_csv", SCRIPT)
merge_csv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_csv)


def csv_bytes(*lines):
    return ("\r\n".join(lines) + "\r\n").encode("iso-8859-1")


def lines(data):
    return data.decode("iso-8859-1").split("\r\n")[:-1]


def test_scrape_log_new_column_local_and_new_rows_from_bot():
    # caso del 2026-11-06: en local se agrego match_format; el bot sumo series y reintento una
    base = csv_bytes("series_id,status", "1,ok", "2,error")
    ours = csv_bytes("series_id,status,match_format", "1,ok,full", "2,error,full", "3,ok,reduced")
    theirs = csv_bytes("series_id,status", "1,ok", "2,ok", "4,ok")
    merged, warnings = merge_csv.merge(base, ours, theirs)
    assert lines(merged) == [
        "series_id,status,match_format", "1,ok,full", "2,ok,full", "3,ok,reduced", "4,ok,",
    ]
    assert warnings == []


def test_raw_csv_groups_by_series_and_prefers_local_on_real_conflict():
    url = "https://www.vlr.gg/{}/x"
    base = csv_bytes("player,source_url", f"lovers,{url.format(1)}")
    ours = csv_bytes("player,source_url", f"lovers rock,{url.format(1)}")  # re-scrape local
    theirs = csv_bytes(
        "player,source_url", f"lovers2,{url.format(1)}", f"a,{url.format(2)}", f"b,{url.format(2)}"
    )
    merged, warnings = merge_csv.merge(base, ours, theirs, "perf.csv")
    assert lines(merged)[1:] == [f"lovers rock,{url.format(1)}", f"a,{url.format(2)}", f"b,{url.format(2)}"]
    assert warnings == ["perf.csv: serie 1 cambio en los dos lados; queda la version local"]


def test_series_deleted_on_one_side_stays_deleted():
    base = csv_bytes("series_id,status", "1,ok", "2,ok")
    ours = csv_bytes("series_id,status", "1,ok")  # purgada en local
    theirs = csv_bytes("series_id,status", "1,ok", "2,ok", "3,ok")
    merged, _ = merge_csv.merge(base, ours, theirs)
    assert lines(merged)[1:] == ["1,ok", "3,ok"]


def test_upload_log_is_union_sorted_and_non_ascii_bytes_survive():
    base = csv_bytes("run_at,table", "2026-11-01,a")
    ours = csv_bytes("run_at,table", "2026-11-01,a", "2026-11-06,b")
    theirs = csv_bytes("run_at,table", "2026-11-01,a", "2026-11-03,c")
    merged, _ = merge_csv.merge(base, ours, theirs)
    assert lines(merged)[1:] == ["2026-11-01,a", "2026-11-03,c", "2026-11-06,b"]

    # utf-8 de "são" y un byte latin-1 suelto pasan intactos
    raw = "series_id,t\r\n1,sÃ£o\r\n2,são\r\n".encode("iso-8859-1")
    assert merge_csv.merge(raw, raw, raw)[0] == raw


@pytest.mark.skipif(shutil.which("git") is None, reason="sin git")
def test_driver_resolves_a_real_git_merge(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    git("config", "merge.vlr-csv.driver", f'"{sys.executable}" "{SCRIPT}" %O %A %B %P')
    (tmp_path / ".gitattributes").write_text("csv/**/*.csv merge=vlr-csv\n")
    log = tmp_path / "csv" / "scrape_log.csv"
    log.parent.mkdir()
    log.write_bytes(csv_bytes("series_id,status", "1,ok", "2,error"))
    git("add", ".")
    git("commit", "-q", "-m", "base")

    git("checkout", "-q", "-b", "bot")
    log.write_bytes(csv_bytes("series_id,status", "1,ok", "2,ok", "4,ok"))
    git("commit", "-q", "-am", "bot")

    git("checkout", "-q", "main")
    log.write_bytes(csv_bytes("series_id,status,match_format", "1,ok,full", "2,error,full", "3,ok,reduced"))
    git("commit", "-q", "-am", "local")

    git("merge", "-q", "--no-edit", "bot")  # sin el driver esto queda en conflicto
    assert lines(log.read_bytes()) == [
        "series_id,status,match_format", "1,ok,full", "2,ok,full", "3,ok,reduced", "4,ok,",
    ]
