"""scripts/relevant_teams.py: validacion de la lista y SQL de teams.relevant."""

import importlib.util
import json
import os
import re

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "relevant_teams.py")
spec = importlib.util.spec_from_file_location("relevant_teams", SCRIPT)
relevant_teams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relevant_teams)

TEAMS = {
    "24636": {"team_id_vlr": "24636", "team_id": "SOLI", "name": "Team Solid"},
    "24401": {"team_id_vlr": "24401", "team_id": "TB3", "name": "TIME DO B3M"},
    "24478": {"team_id_vlr": "24478", "team_id": "SV", "name": "SÓ TEM VELHO"},
    "14461": {"team_id_vlr": "14461", "team_id": "BAR", "name": "Barça eSports"},
}

EVENT_HTML = """
<div class="event-team"><a href="/team/120/100-thieves"><div class="event-team-name">100 Thieves</div></a></div>
<div class="event-team"><a href="/team/2355/kr-esports"><div class="event-team-name">KRÃ\u009c Esports</div></a></div>
<div class="event-team"><div class="event-team-name">TBD</div></div>
<div class="event-team"><div class="event-team-name">TBD</div></div>
"""


def write_json(tmp_path, groups):
    path = tmp_path / "relevant_teams.json"
    path.write_text(json.dumps({"target": "test", "groups": groups}), encoding="utf-8")
    return str(path)


def test_duplicate_id_is_error_and_unknown_or_wrong_name_are_warnings(tmp_path):
    path = write_json(tmp_path, [
        {"name": "BRAZIL", "teams": [
            {"id": "24401", "name": "Team Solid"},     # id equivocado: es TIME DO B3M
            {"id": "24478", "name": "So Tem Velho"},   # acento y mayusculas: coincide
            {"id": "24401", "name": "Time do B3M"},    # repetido
        ]},
        {"name": "EUROPE", "teams": [
            {"id": "14461", "name": "Barca"},          # incluido en "Barça eSports"
            {"id": "18025", "name": "La Masia"},       # no esta en teams
        ]},
    ])
    _, groups = relevant_teams.load_groups(path)
    errors, warnings = relevant_teams.validate(groups, TEAMS)
    assert len(errors) == 1 and "24401" in errors[0] and "repetido" in errors[0]
    assert len(warnings) == 2
    assert any("24401" in w and "TIME DO B3M" in w for w in warnings)
    assert any("18025" in w and "no esta en teams" in w for w in warnings)


def test_sql_has_every_id_once_with_commas(tmp_path):
    path = write_json(tmp_path, [
        {"name": "BRAZIL", "teams": [{"id": "24636", "name": "Team Solid"}, {"id": "24401", "name": "B3M"}]},
        {"name": "EUROPE", "teams": [{"id": "14461", "name": "Barca"}, {"id": "18025", "name": "La Masia"}]},
        {"name": "KICKOFF", "event": "https://www.vlr.gg/event/3178/x", "active": False},
    ])
    data, groups = relevant_teams.load_groups(path, fetch=lambda url: 1 / 0)  # el inactivo no se baja
    sql = relevant_teams.render_sql(data, groups, TEAMS)

    in_list = re.search(r"in \((.*?)\n\);", sql, re.S).group(1)
    code = "\n".join(line.split("--")[0] for line in in_list.splitlines())
    ids = re.findall(r"'(\d+)'", code)
    assert ids == ["24636", "24401", "14461", "18025"]
    # sin comas faltantes: Postgres concatenaria dos strings separados por un salto de linea
    assert re.sub(r"\s+", "", code) == "'24636','24401','14461','18025'"
    assert "set relevant = false;" in sql and sql.index("set relevant = false") < sql.index("set relevant = true")
    assert "begin;" in sql and "commit;" in sql
    assert "3 filas esperadas (4 ids" in sql


def test_parse_event_teams_and_event_group(tmp_path):
    soup = BeautifulSoup(EVENT_HTML, "html.parser")
    teams, tbd = relevant_teams.parse_event_teams(soup)
    assert [t["id"] for t in teams] == ["120", "2355"]
    assert teams[1]["name"] == "KRÜ Esports"
    assert tbd == 2

    path = write_json(tmp_path, [
        {"name": "KICKOFF", "event": "https://www.vlr.gg/event/3178/x",
         "teams": [{"id": "24636", "name": "Team Solid"}]},
    ])
    _, groups = relevant_teams.load_groups(path, fetch=lambda url: soup)
    assert relevant_teams.selected_ids(groups) == ["24636", "120", "2355"]
    _, warnings = relevant_teams.validate(groups, TEAMS)
    assert any("2 slots TBD" in w for w in warnings)


def test_diff():
    current = {
        "24401": {"team_id": "TB3", "name": "TIME DO B3M"},
        "999": {"team_id": "OLD", "name": "Old Team"},
    }
    result = relevant_teams.diff(["24636", "24401"], current, TEAMS)
    assert [r[0] for r in result["entran"]] == ["24636"]
    assert [r[0] for r in result["salen"]] == ["999"]
    assert [r[0] for r in result["quedan"]] == ["24401"]
