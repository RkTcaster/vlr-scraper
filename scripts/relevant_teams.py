"""Genera el SQL que actualiza teams.relevant a partir de relevant_teams.json.

Regla: relevantes son los equipos que van a jugar el proximo torneo importante. Mientras corren los
qualifiers son los que avanzan; cuando arranca el torneo (p.ej. el Americas Kickoff), los equipos de
ese evento. Cada cambio es un reset total: los que no llegaron dejan de ser relevantes.

relevant_teams.json tiene grupos (region / qualifier) con:
- "teams": lista manual de {"id": team_id_vlr, "name": nombre para leer y validar}, o
- "event": url de un evento de vlr; los ids salen de su pagina (.event-team con link /team/<id>/;
  los slots TBD todavia no tienen equipo y solo se informan).
- "active": false deja el grupo cargado sin aplicarlo (p.ej. el kickoff hasta que empiece).

El script no toca Supabase: escribe sql/relevant_teams.sql (una linea por equipo con la coma ya
puesta, todo en una transaccion) para pegarlo en el SQL editor, y muestra que equipos entran y salen
respecto de lo que hoy esta en relevant (lectura de Supabase, --no-db la saltea).

Antes era un SQL a mano: el 2026-11-15 le faltaban 3 comas y Postgres concatena dos strings
separados por un salto de linea ('25222' '12889' -> '2522212889'), asi que 5 equipos quedaban afuera
sin ningun error.

Uso:

    python scripts/relevant_teams.py                 # valida, genera sql/relevant_teams.sql y muestra el diff
    python scripts/relevant_teams.py --no-db         # sin consultar Supabase
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_FILE = os.path.join(ROOT, "relevant_teams.json")
DEFAULT_OUT = os.path.join(ROOT, "sql", "relevant_teams.sql")
DEFAULT_TEAMS = os.path.join(ROOT, "tables", "table_teams.csv")


def real_text(text):
    """Texto de soup_open (utf-8 leido como latin-1, "KRÃ Esports") a texto real ("KRÜ Esports")."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def name_key(name):
    """Nombre comparable: sin acentos, minusculas, solo letras y numeros."""
    ascii_name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def names_match(a, b):
    a, b = name_key(a), name_key(b)
    return bool(a) and bool(b) and (a in b or b in a)


def parse_event_teams(soup):
    """Equipos de la pagina de un evento de vlr.

    Returns:
        tuple: ([{"id", "name"}...] en el orden de la pagina, cantidad de slots TBD)
    """
    teams, tbd = [], 0
    for card in soup.select(".event-team"):
        link = card.select_one("a[href^='/team/']")
        match = re.match(r"/team/(\d+)/", link.get("href", "")) if link else None
        if not match:
            tbd += 1
            continue
        name_node = card.select_one(".event-team-name")
        name = (name_node or link).get_text(" ", strip=True)
        teams.append({"id": match.group(1), "name": real_text(name)})
    return teams, tbd


def load_groups(path, fetch=None):
    """Grupos activos del json, con los equipos de los grupos "event" ya resueltos.

    Args:
        fetch (callable): url -> soup; default vlr_pipeline.fetch.soup_open

    Returns:
        tuple: (data del json, [{"name", "teams", "tbd", "event"}...] solo activos)
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    groups = []
    for group in data.get("groups", []):
        if group.get("active", True) is False:
            continue
        teams = [dict(team) for team in group.get("teams", [])]
        tbd = 0
        if group.get("event"):
            if fetch is None:
                from vlr_pipeline.fetch import soup_open as fetch
            event_teams, tbd = parse_event_teams(fetch(group["event"]))
            teams += event_teams
        groups.append({"name": group["name"], "teams": teams, "tbd": tbd, "event": group.get("event")})
    return data, groups


def read_teams(path):
    """team_id_vlr -> {"team_id", "name"} de tables/table_teams.csv (utf-8, como el resto de tables/)."""
    with open(path, newline="", encoding="utf-8") as f:
        return {row["team_id_vlr"]: row for row in csv.DictReader(f)}


def validate(groups, teams):
    """Returns: (errores, warnings) como listas de strings."""
    errors, warnings = [], []
    seen = {}
    for group in groups:
        for team in group["teams"]:
            team_id = str(team.get("id", "")).strip()
            label = f"{group['name']}: {team_id} {team.get('name', '')}".strip()
            if not re.fullmatch(r"\d+", team_id):
                errors.append(f"{label}: id invalido (tiene que ser el numero de /team/<id>/ de vlr)")
                continue
            if team_id in seen:
                errors.append(f"{label}: id repetido (ya esta en {seen[team_id]})")
                continue
            seen[team_id] = group["name"]
            row = teams.get(team_id)
            if row is None:
                warnings.append(f"{label}: no esta en teams (sin partidos cargados); el UPDATE no lo marca")
            elif team.get("name") and not names_match(team["name"], row["name"]):
                warnings.append(f"{label}: en teams es {row['team_id']} '{row['name']}'; revisar el id")
        if group["tbd"]:
            warnings.append(f"{group['name']}: {group['tbd']} slots TBD en {group['event']} (sin equipo todavia)")
    return errors, warnings


def selected_ids(groups):
    """Ids en orden, sin repetir."""
    ids = []
    for group in groups:
        for team in group["teams"]:
            team_id = str(team["id"]).strip()
            if team_id not in ids:
                ids.append(team_id)
    return ids


def _comment(text):
    return text.replace("\n", " ").replace("*/", "")


def render_sql(data, groups, teams):
    """SQL con reset total + una linea por equipo (la coma la pone el script)."""
    lines = [
        "-- Generado por scripts/relevant_teams.py desde relevant_teams.json. No editar a mano.",
        f"-- {_comment(data.get('target', ''))}",
        "begin;",
        "",
        "update teams",
        "set relevant = false;",
        "",
        "update teams",
        "set relevant = true",
        "where team_id_vlr in (",
    ]
    entries = []
    seen = set()
    for group in groups:
        group_entries = []
        for team in group["teams"]:
            team_id = str(team["id"]).strip()
            if team_id in seen:
                continue
            seen.add(team_id)
            row = teams.get(team_id)
            label = f"{row['team_id']} {row['name']}" if row else f"{team.get('name', '')} (no esta en teams)"
            group_entries.append((team_id, _comment(label)))
        if group_entries:
            entries.append((group["name"], group_entries))

    total = sum(len(group_entries) for _, group_entries in entries)
    count = 0
    for group_name, group_entries in entries:
        lines.append(f"  -- {_comment(group_name)}")
        for team_id, label in group_entries:
            count += 1
            comma = "," if count < total else ""
            lines.append(f"  '{team_id}'{comma}  -- {label}")
    lines += [
        ");",
        "",
        "commit;",
        "",
        f"-- control: {sum(1 for _, e in entries for team_id, _ in e if team_id in teams)} filas esperadas "
        f"({total} ids en la lista)",
        "select team_id_vlr, team_id, name from teams where relevant = true order by team_id;",
        "",
    ]
    return "\n".join(lines)


def diff(selected, current, teams):
    """Compara la lista nueva con los relevant de hoy.

    Args:
        selected (list): ids nuevos
        current (dict): id -> {"team_id", "name"} con relevant = true hoy en Supabase

    Returns:
        dict: entran / salen / quedan, cada uno lista de (id, tag, nombre)
    """
    def describe(team_id):
        row = current.get(team_id) or teams.get(team_id) or {}
        return team_id, row.get("team_id", "?"), row.get("name", "?")

    new = set(selected)
    return {
        "entran": [describe(i) for i in selected if i not in current],
        "salen": [describe(i) for i in sorted(current, key=lambda i: current[i].get("team_id", "")) if i not in new],
        "quedan": [describe(i) for i in selected if i in current],
    }


def fetch_current_relevant():
    from vlr_pipeline import config
    from vlr_pipeline.upload import get_client

    config.load_env_file()
    rows = get_client().table("teams").select("team_id_vlr,team_id,name").eq("relevant", True).execute().data
    return {row["team_id_vlr"]: row for row in rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", default=DEFAULT_FILE)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--teams", default=DEFAULT_TEAMS, help="tables/table_teams.csv (correr process antes)")
    parser.add_argument("--no-db", action="store_true", help="no consulta los relevant actuales en Supabase")
    args = parser.parse_args(argv)

    data, groups = load_groups(args.file)
    teams = read_teams(args.teams)
    errors, warnings = validate(groups, teams)
    for warning in warnings:
        print(f"WARNING {warning}")
    for error in errors:
        print(f"ERROR   {error}")
    if errors:
        print(f"{len(errors)} errores: no se genera el SQL")
        return 1

    ids = selected_ids(groups)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_sql(data, groups, teams))
    for group in groups:
        print(f"{group['name']}: {len(group['teams'])} equipos")
    print(f"{len(ids)} equipos relevantes -> {os.path.relpath(args.out)}")

    if not args.no_db:
        result = diff(ids, fetch_current_relevant(), teams)
        for kind in ("entran", "salen"):
            print(f"\n{kind} ({len(result[kind])}):")
            for team_id, tag, name in result[kind]:
                print(f"  {team_id:>6} {tag:8} {name}")
        print(f"\nse quedan: {len(result['quedan'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
