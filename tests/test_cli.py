"""Exit codes del cli: el workflow hace exit con lo que devuelva python -m vlr_pipeline."""

import json

import pytest

import vlr_pipeline.scraper as scraper
import vlr_pipeline.tables as tables
from vlr_pipeline.cli import main


@pytest.fixture
def events_file(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": [{"name": "x", "url": "https://www.vlr.gg/event/matches/1/x", "active": True}]}))
    return str(path)


def run_all(monkeypatch, tmp_path, events_file, error_count):
    monkeypatch.setattr(scraper, "scrape_all", lambda events, folder, encoding: error_count)
    monkeypatch.setattr(tables, "build_all", lambda csv_dir, tables_dir: None)
    return main(["all", "--events-file", events_file, "--csv-dir", str(tmp_path), "--tables-dir", str(tmp_path), "--skip-upload"])


def test_scrape_errors_exit_0_with_actions_warning(monkeypatch, tmp_path, events_file, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert run_all(monkeypatch, tmp_path, events_file, error_count=3) == 0
    assert "::warning::3 matches terminaron con error" in capsys.readouterr().out


def test_no_actions_annotation_outside_actions(monkeypatch, tmp_path, events_file, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert run_all(monkeypatch, tmp_path, events_file, error_count=3) == 0
    assert "::warning::" not in capsys.readouterr().out


def test_invalid_arguments_fail():
    # argparse sale con 2: antes el workflow lo confundia con "algunos matches fallaron"
    with pytest.raises(SystemExit) as exc:
        main(["all", "--flag-que-no-existe"])
    assert exc.value.code == 2
