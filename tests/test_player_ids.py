"""player_id_vlr: dos jugadores con el mismo nick (785988, dos "Splotza" en RADI) y csv con columnas nuevas."""

import csv

import pandas as pd

from vlr_pipeline.save import append_dict_rows
from vlr_pipeline.tables import agent_key, raw_player_ids, resolve_player_ids, vlr_id_text

# overview del mapa 785988-Haven: dos Splotza en RADI con agentes distintos, y un Reko unico
KEYS = pd.DataFrame({
    "map_id": ["785988-Haven", "785988-Haven", "785988-Haven", "785988-Lotus"],
    "player": ["Splotza", "Splotza", "Reko", "Splotza"],
    "agent_key": ["jett", "omen", "sova", "neon"],
    "player_id_vlr": ["50487", "69551", "69550", "50487"],
})


def test_unique_nick_resolves_without_agent():
    rows = pd.DataFrame({"map_id": ["785988-Haven", "785988-Lotus"], "player": ["Reko", "Splotza"]})
    assert resolve_player_ids(rows, KEYS, "player").tolist() == ["69550", "50487"]


def test_repeated_nick_resolves_by_agent_in_any_case():
    # el overview dice "Jett" y los logs "jett": se comparan en minuscula
    rows = pd.DataFrame({
        "map_id": ["785988-Haven", "785988-Haven"],
        "player": ["Splotza", "Splotza"],
        "agent": ["Omen", "jett"],
    })
    assert resolve_player_ids(rows, KEYS, "player", agent_col="agent").tolist() == ["69551", "50487"]


def test_repeated_nick_without_agent_stays_unresolved():
    # sin agente no hay forma de saber cual Splotza es: NA (y drop_without_player_id lo avisa)
    rows = pd.DataFrame({"map_id": ["785988-Haven"], "player": ["Splotza"]})
    assert resolve_player_ids(rows, KEYS, "player").isna().all()


def test_numeric_nick_matches_across_dtypes():
    keys = pd.DataFrame({"map_id": ["1-Bind"], "player": ["333"], "agent_key": ["jett"], "player_id_vlr": ["7"]})
    rows = pd.DataFrame({"map_id": ["1-Bind"], "player": [333]})  # read_csv lo trae como int
    assert resolve_player_ids(rows, keys, "player").tolist() == ["7"]


def test_ids_and_agents_normalized():
    assert vlr_id_text(pd.Series([69551.0, "50487", None, ""])).tolist()[:2] == ["69551", "50487"]
    assert vlr_id_text(pd.Series([None, ""])).isna().all()
    assert agent_key(pd.Series(["Jett", "jett ", None])).tolist()[:2] == ["jett", "jett"]


def test_append_adds_new_column_without_shifting_old_rows(tmp_path):
    path = tmp_path / "player_stats_x.csv"
    path.write_bytes("player,map\r\nRosÃ©,Bind\r\n".encode("iso-8859-1"))
    original = path.read_bytes()

    append_dict_rows(str(path), {"player": ["Splotza"], "map": ["Haven"], "player_id_vlr": ["69551"]},
                     encoding="iso-8859-1")

    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert rows == [["player", "map", "player_id_vlr"], ["Rosé", "Bind", ""], ["Splotza", "Haven", "69551"]]
    # la fila vieja conserva sus bytes (utf-8 valido), solo se le agrega la columna vacia
    assert path.read_bytes().startswith(b"player,map,player_id_vlr\r\n" + original.split(b"\r\n")[1])


def test_append_fills_columns_the_dict_does_not_have(tmp_path):
    path = tmp_path / "x.csv"
    path.write_bytes(b"a,b,c\r\n1,2,3\r\n")
    append_dict_rows(str(path), {"a": ["4"], "c": ["6"]})
    assert path.read_text(encoding="utf-8").splitlines() == ["a,b,c", "1,2,3", "4,,6"]


def test_player_without_vlr_profile_gets_tbd_id():
    # 784597: "cubinho" (Clov) sale con mod-tbd y sin link /player/ en el overview
    raw = pd.DataFrame({"team": ["Clov", "Clov"], "player": ["cubinho", "Reko"], "player_id_vlr": ["", 69550.0]})
    assert raw_player_ids(raw.replace("", None)).tolist() == ["tbd_Clov_cubinho", "69550"]


def test_player_without_profile_takes_id_from_same_team_and_nick():
    # vlr le creo perfil despues: KH yiyi (KRYO) sin link en un partido y /player/69932 en otro.
    # Dos ids para el mismo (team, nick) (Splotza en RADI) es ambiguo: queda tbd
    raw = pd.DataFrame({
        "team": ["KRYO", "KRYO", "RADI", "RADI", "RADI"],
        "player": ["KH yiyi", "KH yiyi", "Splotza", "Splotza", "Splotza"],
        "player_id_vlr": [None, "69932", "69551", "50487", None],
    })
    assert raw_player_ids(raw).tolist() == ["69932", "69932", "69551", "50487", "tbd_RADI_Splotza"]


def test_team_tags_uppercase_including_non_ascii():
    from vlr_pipeline.tables import upper_tag, upper_team_tags
    # tags en la forma html (utf-8 leido como latin-1): "Mörk" llega como "MÃ¶rk"
    assert upper_tag("Risi") == "RISI"
    assert upper_tag("M\u00c3\u00b6rk").encode("iso-8859-1").decode("utf-8") == "M\u00d6RK"
    assert upper_tag("GEN.GC") == "GEN.GC" and upper_tag(None) is None
    df = upper_team_tags(pd.DataFrame({"team": ["Sun"], "team_a_bank": ["0.1k"], "player": ["cubinho"]}))
    assert df.iloc[0].tolist() == ["SUN", "0.1k", "cubinho"]
