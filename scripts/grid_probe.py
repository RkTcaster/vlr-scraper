"""Prueba de acceso a la API de GRID (Open Access): que titulos, series y campos de Valorant devuelve la key.

Solo lectura, sin dependencias nuevas. La key sale de GRID_API_KEY (entorno o .env.local, via
config.load_env_file) y nunca se imprime.

    python scripts/grid_probe.py                 # resumen
    python scripts/grid_probe.py --dump grid.json  # ademas guarda las respuestas crudas

GRID omite de la respuesta los campos que valen null (no los manda como null): leer siempre con .get().

Endpoints de Open Access (help center de GRID):
    central-data   -> catalogo: titulos, torneos, series, equipos, jugadores (20 req/min)
    series-state   -> estado final de una serie: games (mapas), segments (rondas) (180 req/min, 6 por serie)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vlr_pipeline.config import load_env_file  # noqa: E402

BASE_URL = os.environ.get("GRID_BASE_URL", "https://api-op.grid.gg")
CENTRAL = f"{BASE_URL}/central-data/graphql"
SERIES_STATE = f"{BASE_URL}/live-data-feed/series-state/graphql"

TITLES_QUERY = "query { titles { id name nameShortened } }"

SERIES_QUERY = """
query ($titleId: ID!) {
  allSeries(first: 5, filter: { titleId: $titleId }, orderBy: StartTimeScheduled, orderDirection: DESC) {
    totalCount
    edges { node {
      id startTimeScheduled
      tournament { id name }
      teams { baseInfo { id name nameShortened } }
    } }
  }
}
"""

STATE_QUERY = """
query ($id: ID!) {
  seriesState(id: $id) {
    id started finished valid
    teams { id name won score kills deaths }
    games { id map { name } segments { id } }
  }
}
"""

# Introspeccion: que tipos especificos de Valorant expone el schema de series-state
TYPES_QUERY = "query { __schema { types { name } } }"

FIELDS_QUERY = """
query ($name: String!) {
  __type(name: $name) {
    kind
    fields { name type { kind name ofType { kind name ofType { kind name ofType { kind name } } } } }
    enumValues { name }
    possibleTypes { name }
  }
}
"""


def post(url, query, variables=None, key=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "x-api-key": key,
        "User-Agent": "grid-probe",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"http_error": exc.code, "body": exc.read().decode(errors="replace")[:500]}


def errors_of(resp):
    if "http_error" in resp:
        return f"HTTP {resp['http_error']}: {resp['body']}"
    if resp.get("errors"):
        return "; ".join(e.get("message", str(e)) for e in resp["errors"])
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dump", help="archivo json donde guardar las respuestas crudas")
    args = parser.parse_args()

    load_env_file()
    key = os.environ.get("GRID_API_KEY")
    if not key:
        sys.exit("Falta GRID_API_KEY (agregala a .env.local)")

    dump = {}
    try:
        probe(key, dump)
    finally:
        # Se guarda aunque algo falle a mitad de camino: la respuesta cruda es lo que sirve para depurar
        if args.dump:
            with open(args.dump, "w", encoding="utf-8") as fh:
                json.dump(dump, fh, indent=2, ensure_ascii=False)
            print(f"\nRespuestas crudas en {args.dump}")


def probe(key, dump):

    titles = post(CENTRAL, TITLES_QUERY, key=key)
    dump["titles"] = titles
    if err := errors_of(titles):
        print(f"central-data titles: {err}")
        return
    title_list = titles["data"]["titles"]
    print("Titulos visibles con esta key:")
    for t in title_list:
        print(f"  {t['id']:>4}  {t['name']}")

    valorant = next((t for t in title_list if "valorant" in t["name"].lower()), None)
    if valorant is None:
        print("\nValorant NO aparece entre los titulos: la key no cubre Valorant.")
    else:
        series = post(CENTRAL, SERIES_QUERY, {"titleId": valorant["id"]}, key=key)
        dump["series"] = series
        if err := errors_of(series):
            print(f"\ncentral-data allSeries: {err}")
        else:
            data = series["data"]["allSeries"]
            print(f"\nSeries de Valorant: {data['totalCount']} en total. Las ultimas:")
            for edge in data["edges"]:
                n = edge["node"]
                teams = " vs ".join(t["baseInfo"]["name"] for t in n["teams"])
                print(f"  {n['id']:>8}  {n['startTimeScheduled']}  {n['tournament']['name']}  |  {teams}")

            # La primera serie terminada que devuelva estado
            for edge in data["edges"]:
                sid = edge["node"]["id"]
                state = post(SERIES_STATE, STATE_QUERY, {"id": sid}, key=key)
                dump.setdefault("series_state", {})[sid] = state
                if err := errors_of(state):
                    print(f"\nseries-state {sid}: {err}")
                    continue
                s = (state.get("data") or {}).get("seriesState")
                if s is None:
                    # Respuesta sin seriesState ni errors: se muestra tal cual para ver el formato real
                    print(f"\nseries-state {sid}: respuesta inesperada: {json.dumps(state)[:500]}")
                    continue
                if not s["finished"]:
                    print(f"\nseries-state {sid}: todavia no termino (started={s['started']})")
                    continue
                print(f"\nseries-state {sid}: finished={s['finished']} valid={s['valid']}")
                for t in s["teams"]:
                    print(f"  {t['name']}: score {t['score']}, kills {t['kills']}, won={t['won']}")
                for g in s["games"]:
                    print(f"  game {g['id']}: {g['map']['name']}, {len(g['segments'])} segments (rondas)")
                break

    types = post(SERIES_STATE, TYPES_QUERY, key=key)
    if err := errors_of(types):
        print(f"\nintrospeccion series-state: {err}")
    else:
        names = sorted(t["name"] for t in types["data"]["__schema"]["types"] if "valorant" in t["name"].lower())
        dump["valorant_types"] = names
        print("\nTipos de Valorant en series-state:", ", ".join(names) or "(ninguno)")

        # Campos de cada tipo: es lo que se puede pedir con `... on <Tipo> { ... }`
        dump["valorant_fields"] = {}
        for name in names:
            resp = post(SERIES_STATE, FIELDS_QUERY, {"name": name}, key=key)
            if err := errors_of(resp):
                print(f"  {name}: {err}")
                continue
            fields = [f"{f['name']}: {type_label(f['type'])}" for f in (resp["data"]["__type"] or {}).get("fields") or []]
            dump["valorant_fields"][name] = fields
            print(f"\n{name}:\n  " + "\n  ".join(fields))

        nested_types(names, key, dump)

    win_types(key, dump)


def base_type(t):
    """Tipo final de un campo, sin NON_NULL ni LIST: (kind, name)."""
    while t["kind"] in ("NON_NULL", "LIST"):
        t = t["ofType"]
    return t["kind"], t["name"]


def nested_types(roots, key, dump, limit=60):
    """Recorre (BFS) los tipos no escalares a los que llegan los tipos de Valorant.

    Para OBJECT / INTERFACE lista los campos, para ENUM los valores, para UNION / INTERFACE los tipos posibles.
    Es lo que hace falta saber antes de pedir, por ejemplo, `weaponKills { ... }` en una query.
    """
    seen = set(roots)
    queue = list(roots)
    out = {}
    while queue and len(out) < limit:
        name = queue.pop(0)
        resp = post(SERIES_STATE, FIELDS_QUERY, {"name": name}, key=key)
        t = (resp.get("data") or {}).get("__type")
        if errors_of(resp) or not t:
            continue
        for f in t.get("fields") or []:
            kind, child = base_type(f["type"])
            if kind not in ("SCALAR",) and child not in seen:
                seen.add(child)
                queue.append(child)
        # De una interfaz (p. ej. Objective) solo interesan sus variantes de Valorant
        for p in t.get("possibleTypes") or []:
            if "valorant" in p["name"].lower() and p["name"] not in seen:
                seen.add(p["name"])
                queue.append(p["name"])
        if name in roots:
            continue  # ya impresos arriba
        info = {"kind": t["kind"]}
        if t.get("fields"):
            info["fields"] = [f"{f['name']}: {type_label(f['type'])}" for f in t["fields"]]
        if t.get("enumValues"):
            info["values"] = [v["name"] for v in t["enumValues"]]
        if t.get("possibleTypes"):
            info["possible"] = [p["name"] for p in t["possibleTypes"]]
        out[name] = info
    dump["nested_types"] = out
    print("\n=== Tipos anidados ===")
    for name, info in out.items():
        print(f"\n{name} ({info['kind']}):")
        for field in info.get("fields", []):
            print(f"  {field}")
        if "values" in info:
            print(f"  valores: {', '.join(info['values'])}")
        if "possible" in info:
            print(f"  tipos posibles: {', '.join(info['possible'])}")


WIN_TYPE_QUERY = """
query ($id: ID!) {
  seriesState(id: $id) {
    games { map { name } segments { id teams { ... on SegmentTeamStateValorant { name side won winType } } } }
  }
}
"""


def win_types(key, dump, series_id="3003317"):
    """Valores reales de winType (es String en el schema, no enum): se cuentan en una serie terminada."""
    resp = post(SERIES_STATE, WIN_TYPE_QUERY, {"id": series_id}, key=key)
    dump["win_types_sample"] = resp
    if err := errors_of(resp):
        print(f"\nwinType {series_id}: {err}")
        return
    counts = {}
    for g in resp["data"]["seriesState"]["games"]:
        for seg in g["segments"]:
            for t in seg["teams"]:
                if t.get("won"):
                    k = (t.get("side"), t.get("winType"))
                    counts[k] = counts.get(k, 0) + 1
    print(f"\nwinType de las rondas ganadas en {series_id} (side, winType: rondas):")
    for (side, wt), n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {side:<10} {wt:<30} {n}")


def type_label(t):
    """`[Int!]!` a partir del arbol kind/ofType de la introspeccion."""
    if t["kind"] == "NON_NULL":
        return type_label(t["ofType"]) + "!"
    if t["kind"] == "LIST":
        return "[" + type_label(t["ofType"]) + "]"
    return t["name"]


if __name__ == "__main__":
    main()
