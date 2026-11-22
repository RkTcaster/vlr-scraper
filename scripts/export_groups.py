"""Exporta standings.csv y h2h.csv de fase de grupos (contrato en handoff/archivado/INPUT_CONTRACT.md).

Era la seccion "Export INPUT_CONTRACT" de csv_process.ipynb (borrada el 2026-11-16); la logica no cambio.

Inputs:
- tables/table_round_info.csv (fuente unica de scores)
- tables/table_tournament.csv + tables/table_region.csv (region por tour_id)
- tables/table_groups.csv: mapping manual `tour_id, team, group`. Un torneo sin filas ahi no se exporta.

Output: intermediate/groups/standings.csv y h2h.csv. `tournament` = tour_id completo; fixture.csv es manual.

    python -m vlr_pipeline process
    python scripts/export_groups.py [--tables tables] [--out intermediate/groups]
"""

import argparse
import os
import sys

import pandas as pd


def read_inputs(tables):
    # round_info se escribe con iso-8859-1 pero los bytes en disco son utf-8 validos (ver "Encoding"
    # en CLAUDE.md): se lee como utf-8 para que los tags coincidan con table_groups.csv (utf-8 nativo).
    def read(name):
        return pd.read_csv(os.path.join(tables, name), encoding="utf-8")

    df_groups = read("table_groups.csv")
    df_groups = df_groups.dropna(subset=["group"])
    df_groups = df_groups[df_groups["group"].astype(str).str.strip() != ""]
    return read("table_round_info.csv"), read("table_tournament.csv"), read("table_region.csv"), df_groups


def build_series(df_round_info):
    """Una fila por serie: ganador, perdedor, mapas y rondas de cada uno."""
    map_score = (
        df_round_info.groupby(["tour_id", "series_id", "map_id"], as_index=False)
        .agg(teamA=("teamA", "first"),
             teamB=("teamB", "first"),
             scoreA=("rndA", "sum"),
             scoreB=("rndB", "sum"))
    )
    map_score["map_winner"] = map_score.apply(
        lambda r: r["teamA"] if r["scoreA"] > r["scoreB"] else r["teamB"], axis=1
    )

    series_rows = []
    for (tour_id, series_id), grp in map_score.groupby(["tour_id", "series_id"]):
        teams = pd.unique(grp[["teamA", "teamB"]].values.ravel())
        if len(teams) != 2:
            print(f"[skip] series {series_id} ({tour_id}) has unexpected team set: {teams}")
            continue
        t1, t2 = teams[0], teams[1]
        maps_won = {t1: int((grp["map_winner"] == t1).sum()),
                    t2: int((grp["map_winner"] == t2).sum())}
        rounds_won = {t1: 0, t2: 0}
        for _, row in grp.iterrows():
            if row["teamA"] == t1:
                rounds_won[t1] += int(row["scoreA"])
                rounds_won[t2] += int(row["scoreB"])
            else:
                rounds_won[t2] += int(row["scoreA"])
                rounds_won[t1] += int(row["scoreB"])

        if maps_won[t1] == maps_won[t2]:
            print(f"[warn] series {series_id} tied on maps {maps_won}; skipping")
            continue
        winner = t1 if maps_won[t1] > maps_won[t2] else t2
        loser = t2 if winner == t1 else t1
        series_rows.append({
            "tour_id": tour_id,
            "series_id": series_id,
            "winner": winner,
            "loser": loser,
            "winner_maps": maps_won[winner],
            "loser_maps": maps_won[loser],
            "winner_rounds": rounds_won[winner],
            "loser_rounds": rounds_won[loser],
        })
    return pd.DataFrame(series_rows)


def build_standings_h2h(df_series, df_tour, df_reg, df_groups):
    """standings (por tour_id, team) y h2h (solo el lado ganador), filtrados a table_groups."""
    winners = df_series.rename(columns={
        "winner": "team", "loser": "opponent",
        "winner_maps": "team_maps", "loser_maps": "opp_maps",
        "winner_rounds": "team_rounds", "loser_rounds": "opp_rounds",
    }).assign(result=1)
    losers = df_series.rename(columns={
        "loser": "team", "winner": "opponent",
        "loser_maps": "team_maps", "winner_maps": "opp_maps",
        "loser_rounds": "team_rounds", "winner_rounds": "opp_rounds",
    }).assign(result=0)
    per_team_series = pd.concat([winners, losers], ignore_index=True)

    standings = (
        per_team_series.groupby(["tour_id", "team"], as_index=False)
        .agg(
            wins=("result", "sum"),
            loss=("result", lambda s: int((s == 0).sum())),
            matchWins=("team_maps", "sum"),
            matchLoss=("opp_maps", "sum"),
            roundWin=("team_rounds", "sum"),
            roundLoss=("opp_rounds", "sum"),
        )
    )
    for col in ["wins", "loss", "matchWins", "matchLoss", "roundWin", "roundLoss"]:
        standings[col] = standings[col].astype(int)

    h2h = pd.DataFrame({
        "tour_id": df_series["tour_id"],
        "team": df_series["winner"],
        "opponent": df_series["loser"],
        "md": (df_series["winner_maps"] - df_series["loser_maps"]).astype(int),
        "rd": (df_series["winner_rounds"] - df_series["loser_rounds"]).astype(int),
    })

    # solo torneos + equipos presentes en table_groups.csv (semi-join de los dos lados)
    valid = df_groups[["tour_id", "team"]]
    standings = standings.merge(df_groups, on=["tour_id", "team"], how="inner")
    h2h = (
        h2h.merge(valid, on=["tour_id", "team"], how="inner")
           .merge(valid.rename(columns={"team": "opponent"}), on=["tour_id", "opponent"], how="inner")
    )
    # el grupo del h2h es el del ganador (team)
    h2h = h2h.merge(df_groups, on=["tour_id", "team"], how="left")

    reg_lookup = df_tour.merge(df_reg, on="reg_id", how="left")[["tour_id", "region"]]
    standings = standings.merge(reg_lookup, on="tour_id", how="left")
    h2h = h2h.merge(reg_lookup, on="tour_id", how="left")

    standings = standings.rename(columns={"tour_id": "tournament", "team": "name"})
    h2h = h2h.rename(columns={"tour_id": "tournament"})
    standings = standings[["tournament", "region", "group", "name",
                           "wins", "loss", "matchWins", "matchLoss", "roundWin", "roundLoss"]]
    h2h = h2h[["tournament", "region", "group", "team", "opponent", "md", "rd"]]
    return standings, h2h


def cross_check(standings, h2h):
    """Cross-checks de la seccion 5 del INPUT_CONTRACT; devuelve la lista de diferencias."""
    errors = []
    for (tournament, group), s_grp in standings.groupby(["tournament", "group"]):
        h_grp = h2h[(h2h["tournament"] == tournament) & (h2h["group"] == group)]
        for _, row in s_grp.iterrows():
            team = row["name"]
            won = h_grp["team"] == team
            lost = h_grp["opponent"] == team
            checks = [
                ("h2h rows", (won | lost).sum(), "wins+loss", int(row["wins"] + row["loss"])),
                ("md sum", h_grp.loc[won, "md"].sum() - h_grp.loc[lost, "md"].sum(),
                 "matchWins-matchLoss", int(row["matchWins"] - row["matchLoss"])),
                ("rd sum", h_grp.loc[won, "rd"].sum() - h_grp.loc[lost, "rd"].sum(),
                 "roundWin-roundLoss", int(row["roundWin"] - row["roundLoss"])),
            ]
            for got_name, got, expected_name, expected in checks:
                if got != expected:
                    errors.append(f"{tournament}/{group}/{team}: {got_name}={got} vs {expected_name}={expected}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tables", default="tables")
    parser.add_argument("--out", default=os.path.join("intermediate", "groups"))
    args = parser.parse_args(argv)

    groups_path = os.path.join(args.tables, "table_groups.csv")
    if not os.path.exists(groups_path):
        print(f"falta {groups_path} (mapping manual tour_id, team, group): nada para exportar")
        return 1

    df_round_info, df_tour, df_reg, df_groups = read_inputs(args.tables)
    df_series = build_series(df_round_info)
    print(f"series aggregated: {len(df_series)}")
    standings, h2h = build_standings_h2h(df_series, df_tour, df_reg, df_groups)

    errors = cross_check(standings, h2h)
    if errors:
        for error in errors:
            print("  ", error)
        print(f"{len(errors)} cross-check failures: no se escribe nada")
        return 1
    print("cross-checks OK")

    os.makedirs(args.out, exist_ok=True)
    for name, df in (("standings.csv", standings), ("h2h.csv", h2h)):
        path = os.path.join(args.out, name)
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"wrote {path} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
