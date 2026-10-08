"""Extractores de un match de vlr.gg (vlr_scraper.ipynb celda 2)."""

import json
import logging
import re

from vlr_pipeline.fetch import soup_open
from vlr_pipeline.save import save_round_detail_to_csv

logger = logging.getLogger(__name__)


def parse_map_name(map_div):
    """extract the map name from a div.map block

    El style del span cambia cada tanto (hoy "position: relative; display: inline-block;"),
    asi que matcheamos por substring en vez de por string exacto.

    Args:
        map_div (bs4.element.Tag): div con class="map"

    Returns:
        str | None: nombre del mapa, o None si el span no esta
    """
    span = map_div.find("span", style=lambda value: value and "position: relative" in value)
    if span is None:
        return None
    text = span.find(string=True, recursive=False)
    return text.strip() if text else None


def get_basic_match_info(soup, url):
    """extract the basic match info from the vlr match page, used in other functions and for check the match status:
        ["team_a"
        "team_b"
        "team_a_tricode"
        "team_b_tricode"
        "event"
        "status"
        "bo"
        "date"
        "patch"
        "tournament_instance"
        "type"
        "source_url" ]


    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info

    Returns:
        dict: basict match info from dict
    """
    basic_match_info = {
        "teams": None,
        "event": None,
        "tournament_instance": None,
        "type": None,
    }

    event_text = soup.find("title").get_text(strip=True)
    regex = r"^([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)$"
    result = re.search(regex, event_text)

    for index, key in enumerate(basic_match_info.keys(), 1):
        basic_match_info[key] = result.group(index).strip()

    team_dict = {
        "team_a": None,
        "team_b": None,
        "team_a_tricode": None,
        "team_b_tricode": None,
        "event": None,
        "status": None,
        "bo": None,
        "date": None,
        "patch": None,
        "tournament_instance": None,
        "type": None,
        "source_url": None
    }

    event = basic_match_info["event"]

    team_dict["tournament_instance"] = basic_match_info["tournament_instance"]
    team_dict["type"] = basic_match_info["type"]

    teams_string = basic_match_info["teams"]
    pattern = r"^(.+?)\s+vs\.\s+(.+)$"

    result = re.findall(pattern, teams_string)

    teams = list(result[0]) if result else []
    team_tricodes = soup.find_all("div", {"class": "team"})

    if team_dict["team_a"] is not None:
        pass

    else:
        teamA_tricode = team_tricodes[2].get_text(strip=True)

        team_dict["team_a"] = teams[0]
        team_dict["team_a_tricode"] = teamA_tricode.strip()
        team_dict["event"] = event

    if team_dict["team_b"] is not None:
        pass
    else:
        teamB_tricode = team_tricodes[3].get_text(strip=True)

        team_dict["team_b"] = teams[1]
        team_dict["team_b_tricode"] = teamB_tricode.strip()

    match_notes = soup.find_all("div", {"class": "match-header-vs-note"})
    team_dict["status"] = match_notes[0].get_text().strip()
    team_dict["bo"] = match_notes[1].get_text().strip()[-1]

    # Header info
    header = soup.find("div", {"class": "match-header-super"})

    date = soup.find_all("div", class_="moment-tz-convert")[0].get("data-utc-ts")
    try:
        patch = header.find("div", style="font-style: italic;").get_text(strip=True)
    except Exception as e:
        logger.warning(f"Error in patch{e}")
        patch = "No patch"

    team_dict["date"] = date
    team_dict["patch"] = patch
    team_dict["source_url"] = url

    return team_dict


# Map draft:
def get_map_draft(soup):
    """pre step to process

    vlr reusa el div match-header-note para avisos del match (p.ej. "Map 3 stats are
    incomplete due to lobby remake."), asi que puede haber mas de uno y el draft no ser
    el primero. Nos quedamos con el que tiene forma de draft.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info

    Returns:
        list | None: list with all the maps, o None si no hay nota de draft
    """
    for note in soup.find_all("div", {"class": "match-header-note"}):
        text = note.get_text(strip=True)
        if ";" in text and ("ban" in text or "pick" in text or "remains" in text):
            return [x.strip() for x in text.split(sep=";")]

    logger.warning("no encontre la nota de draft en el match")
    return None


def get_picks_bans(soup, basic_match_info=None):
    """get the picks and bans from a vlr match page

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info
        basic_match_info (dict, optional): basic match info dict. Defaults to None.

    Returns:
        dict: daft dict
    """
    if basic_match_info is None:
        logger.warning("Add basic_match_info dict")

    picks_bans = get_map_draft(soup)
    if not picks_bans:
        return None

    dict_picks_bans = {
        "header": [
            "team",
            "rival",
            "team_1_select_1",
            "team_2_select_1",
            "team_1_select_2",
            "team_2_select_2",
            "team_1_select_3",
            "team_2_select_3",
            "decider",
            "order",
            "bo",
            "date",
            "source_url",
            "event",
        ],
        "team_A": [],
        "team_B": [],
    }

    team_list_temp = []
    for element in picks_bans[0:-1]:
        list_elements = element.split()
        team_list_temp.append(list_elements[0])
    team_list = list(dict.fromkeys(team_list_temp))
    dict_picks_bans["team_A"].append(team_list[0])
    dict_picks_bans["team_A"].append(team_list[1])
    dict_picks_bans["team_B"].append(team_list[1])
    dict_picks_bans["team_B"].append(team_list[0])

    while len(picks_bans) < 7:
        picks_bans.append("NA")

    for element in picks_bans:
        list_element = element.split()
        if len(list_element) == 3:
            dict_picks_bans["team_A"].append(list_element[-1])
        if len(list_element) == 2:
            dict_picks_bans["team_A"].append(list_element[0])
        if len(list_element) == 1:
            dict_picks_bans["team_A"].append(list_element[0])
    order_team_B = [1, 0, 3, 2, 5, 4, 6]  # for order swaping
    maps_teamA = dict_picks_bans["team_A"][2:]

    try:
        map_order = [maps_teamA[i] for i in order_team_B]
    except IndexError:
        logger.warning(f"IndexError in get_picks_bans: {maps_teamA}")
        return None

    for map in map_order:
        dict_picks_bans["team_B"].append(map)

    dict_picks_bans["team_A"].append("A")
    dict_picks_bans["team_B"].append("B")

    bo = basic_match_info["bo"]

    dict_picks_bans["team_A"].append(bo)
    dict_picks_bans["team_B"].append(bo)

    date = basic_match_info["date"]
    dict_picks_bans["team_A"].append(date)
    dict_picks_bans["team_B"].append(date)

    url = basic_match_info["source_url"]

    dict_picks_bans["team_A"].append(url)
    dict_picks_bans["team_B"].append(url)

    event = basic_match_info["event"]

    dict_picks_bans["team_A"].append(event)
    dict_picks_bans["team_B"].append(event)

    return dict_picks_bans


# Round detail


def round_detail_to_dict(round_detail, folder="csv", encoding="utf-8"):
    """process the get_round_detail() dict to a valid format and save the csv

    Args:
        round_detail (dict): dict from get_round_detail()
    """
    round_detail_for_csv = {
        "teamA": [],
        "map": [],
        "side": [],
        "teamB": [],
        "rndA": [],
        "rndB": [],
        "round": [],
        "winCon": [],
        "date": [],
        "map_order": [],
        "event": [],
        "source_url": [],
    }

    for count, rondaAtk in enumerate(round_detail["teamATT"]):
        round_detail_for_csv["teamA"].append(round_detail["team_a"])
        round_detail_for_csv["teamB"].append(round_detail["team_b"])
        round_detail_for_csv["side"].append("atk")
        round_detail_for_csv["rndA"].append(rondaAtk)
        round_detail_for_csv["rndB"].append(round_detail["teamBCT"][count])
        round_detail_for_csv["map"].append(round_detail["map"])
        round_detail_for_csv["round"].append(round_detail["ratk"][count])
        round_detail_for_csv["winCon"].append(round_detail["winConAtk"][count])
        round_detail_for_csv["date"].append(round_detail["date"])
        round_detail_for_csv["map_order"].append(round_detail["map_order"])
        round_detail_for_csv["event"].append(round_detail["event"])
        round_detail_for_csv["source_url"].append(round_detail["source_url"])

    for count, rondaDef in enumerate(round_detail["teamACT"]):
        round_detail_for_csv["teamA"].append(round_detail["team_a"])
        round_detail_for_csv["teamB"].append(round_detail["team_b"])
        round_detail_for_csv["side"].append("def")
        round_detail_for_csv["rndA"].append(rondaDef)
        round_detail_for_csv["rndB"].append(round_detail["teamBTT"][count])
        round_detail_for_csv["map"].append(round_detail["map"])
        round_detail_for_csv["round"].append(round_detail["rdef"][count])
        round_detail_for_csv["winCon"].append(round_detail["winConDef"][count])
        round_detail_for_csv["date"].append(round_detail["date"])
        round_detail_for_csv["map_order"].append(round_detail["map_order"])
        round_detail_for_csv["event"].append(round_detail["event"])
        round_detail_for_csv["source_url"].append(round_detail["source_url"])

    save_round_detail_to_csv(round_detail_for_csv, folder=folder, encoding=encoding)


def get_round_detail(soup, basic_match_info=None, folder="csv", encoding="utf-8"):
    """extract round info from a vlr match.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info
        basic_match_info (dict, optional): basic match info dict. Defaults to None.

    Returns:
        dict: round info dict
    """
    if basic_match_info is None:
        logger.warning("basic_match_info required")

    round_info = {
        "team_a": None,
        "team_b": None,
        "map": None,
        "teamACT": [],
        "teamATT": [],
        "teamBCT": [],
        "teamBTT": [],
        "ratk": [],
        "rdef": [],
        "winConAtk": [],
        "winConDef": [],
        "date": None,
        "map_order": None,
        "event": None,
        "source_url": None
    }

    maps = []

    map_div = soup.find_all("div", class_="map")

    for map in map_div:
        map_name = parse_map_name(map)
        if map_name is None:
            continue  # bloque sin nombre de mapa: no lo contamos para no desalinear maps[]
        maps.append(map_name)

    bloques = soup.find_all("div", class_="vlr-rounds-row-col")
    control_value = 0
    mapNumber = 0

    round_info["date"] = basic_match_info["date"]
    round_info["map"] = maps[mapNumber]
    round_info["map_order"] = mapNumber

    round_info["event"] = basic_match_info["event"]

    round_info["source_url"] = basic_match_info["source_url"]

    for count, ronda in enumerate(bloques):
        try:
            round_info["team_a"] = basic_match_info["team_a_tricode"]
            round_info["team_b"] = basic_match_info["team_b_tricode"]
            value = int(ronda.find_all("div", class_="rnd-num")[0].text.strip())
            imgUrl = str(ronda.find_all("img")[0])
            victory_condition = imgUrl[0:-3].split("/")[-1].rstrip(".webp")

            if value >= control_value:
                control_value = value
                round_for_eval = re.findall(r"rnd-sq(.*)", str(bloques[count]))
                if round_for_eval[0] == ' mod-win mod-ct">':
                    round_info["teamACT"].append(1)
                    round_info["teamBTT"].append(0)
                    round_info["rdef"].append(value)
                    round_info["winConDef"].append(victory_condition)
                elif round_for_eval[0] == ' mod-win mod-t">':
                    round_info["teamATT"].append(1)
                    round_info["teamBCT"].append(0)
                    round_info["ratk"].append(value)
                    round_info["winConAtk"].append(victory_condition)
                if round_for_eval[1] == ' mod-win mod-ct">':
                    round_info["teamBCT"].append(1)
                    round_info["teamATT"].append(0)
                    round_info["ratk"].append(value)
                    round_info["winConAtk"].append(victory_condition)
                elif round_for_eval[1] == ' mod-win mod-t">':
                    round_info["teamBTT"].append(1)
                    round_info["teamACT"].append(0)
                    round_info["rdef"].append(value)
                    round_info["winConDef"].append(victory_condition)

            else:
                mapNumber += 1
                control_value = value
                round_detail_to_dict(round_info, folder=folder, encoding=encoding)
                round_info = {
                    "team_a": None,
                    "team_b": None,
                    "map": None,
                    "teamACT": [],
                    "teamATT": [],
                    "teamBCT": [],
                    "teamBTT": [],
                    "ratk": [],
                    "rdef": [],
                    "winConAtk": [],
                    "winConDef": [],
                    "date": None,
                    "map_order": None,
                    "event": None,
                    "source_url": None
                }

                round_info["team_a"] = basic_match_info["team_a_tricode"]
                round_info["team_b"] = basic_match_info["team_b_tricode"]
                round_info["source_url"] = basic_match_info["source_url"]

                round_info["map_order"] = mapNumber
                round_info["map"] = maps[mapNumber]
                round_for_eval = re.findall(r"rnd-sq(.*)", str(bloques[count]))
                imgUrl = str(ronda.find_all("img")[0])
                victory_condition = imgUrl[0:-3].split("/")[-1].rstrip(".webp")

                round_info["date"] = basic_match_info["date"]
                round_info["event"] = basic_match_info["event"]

                if round_for_eval[0] == ' mod-win mod-ct">':
                    round_info["teamACT"].append(1)
                    round_info["teamBTT"].append(0)
                    round_info["rdef"].append(value)
                    round_info["winConDef"].append(victory_condition)
                elif round_for_eval[0] == ' mod-win mod-t">':
                    round_info["teamATT"].append(1)
                    round_info["teamBCT"].append(0)
                    round_info["ratk"].append(value)
                    round_info["winConAtk"].append(victory_condition)
                if round_for_eval[1] == ' mod-win mod-ct">':
                    round_info["teamBCT"].append(1)
                    round_info["teamATT"].append(0)
                    round_info["ratk"].append(value)
                    round_info["winConAtk"].append(victory_condition)
                elif round_for_eval[1] == ' mod-win mod-t">':
                    round_info["teamBTT"].append(1)
                    round_info["teamACT"].append(0)
                    round_info["rdef"].append(value)
                    round_info["winConDef"].append(victory_condition)

        except:
            pass
    round_detail_to_dict(round_info, folder=folder, encoding=encoding)
    return round_info


def get_player_performance(url, basic_match_info):
    """extract the player performance from a vlr match performance tab

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info
        basic_match_info (dict, optional): basic match info dict. Defaults to None.

    Returns:
        dict: player performance dict
    """
    performance_dict = {
        "player": [],
        "team": [],
        "2K": [],
        "3K": [],
        "4K": [],
        "5K": [],
        "1v1": [],
        "1v2": [],
        "1v3": [],
        "1v4": [],
        "1v5": [],
        "ECON": [],
        "PL": [],
        "DE": [],
        "map": [],
        "date": [],
        "source_url": [],
        "event": [],
    }

    performance_tab = "/?game=all&tab=performance"

    url_performance = url + performance_tab

    soup_performance = soup_open(url_performance)

    bo = int(basic_match_info["bo"])  # Could be not necesary to do this check

    status = basic_match_info["status"]

    if status == "final" and (bo == 3 or bo == 5):
        get_games_id = soup_performance.find_all("div", {"class": "vm-stats-game"})
        game_ids = [
            div.get("data-game-id")
            for div in get_games_id
            if div.has_attr("data-game-id")
        ]

        # vlr agrega clases y espacios sobrantes al nav item
        # ("... js-map-switch  mod-disabled    "), asi que matcheamos por clase
        # individual con select() y no por el string exacto del atributo class.
        # El item "All Maps" tambien tiene js-map-switch, asi que mapeamos por
        # data-game-id en vez de por posicion: si no, todos los nombres se corren
        # un lugar.
        map_by_game_id = {}
        for item in soup_performance.select(".vm-stats-gamesnav-item.js-map-switch"):
            game_id = item.get("data-game-id")
            if not game_id:
                continue
            if game_id == "all":
                map_by_game_id[game_id] = "all"
            else:
                # el texto viene como "1Abyss": sacamos el numero de orden
                map_by_game_id[game_id] = re.sub(r"^\d+", "", item.get_text(strip=True))

        for id in game_ids:
            div = soup_performance.find(
                "div", {"class": "vm-stats-game", "data-game-id": id}
            )
            test_div = div.find_all("tr")[1:]
            pre_process = []
            for element in test_div:
                if len(element) > 13:
                    pre_process.append(element)

            filas = pre_process[1:]

            for fila in filas:
                celdas = fila.find_all("td")

                if len(celdas) > 0:  # Check if info is valid (map is played)

                    jugador_div = celdas[0].find("div").find_all("div")[0]

                    nombre_jugador = jugador_div.get_text().split()

                    def extraer_numero(text):
                        match = re.match(r"^\d+", text)
                        return int(match.group()) if match else 0

                    performance_dict["player"].append(nombre_jugador[0])
                    performance_dict["team"].append(nombre_jugador[1])
                    performance_dict["2K"].append(
                        extraer_numero(celdas[2].get_text(strip=True))
                    )
                    performance_dict["3K"].append(
                        extraer_numero(celdas[3].get_text(strip=True))
                    ),
                    performance_dict["4K"].append(
                        extraer_numero(celdas[4].get_text(strip=True))
                    ),
                    performance_dict["5K"].append(
                        extraer_numero(celdas[5].get_text(strip=True))
                    ),
                    performance_dict["1v1"].append(
                        extraer_numero(celdas[6].get_text(strip=True))
                    ),
                    performance_dict["1v2"].append(
                        extraer_numero(celdas[7].get_text(strip=True))
                    ),
                    performance_dict["1v3"].append(
                        extraer_numero(celdas[8].get_text(strip=True))
                    ),
                    performance_dict["1v4"].append(
                        extraer_numero(celdas[9].get_text(strip=True))
                    ),
                    performance_dict["1v5"].append(
                        extraer_numero(celdas[10].get_text(strip=True))
                    ),
                    performance_dict["ECON"].append(
                        extraer_numero(celdas[11].get_text(strip=True))
                    ),
                    performance_dict["PL"].append(
                        extraer_numero(celdas[12].get_text(strip=True))
                    ),
                    performance_dict["DE"].append(
                        extraer_numero(celdas[13].get_text(strip=True))
                    )
                    performance_dict["date"].append(basic_match_info["date"])
                    performance_dict["event"].append(basic_match_info["event"])
                    performance_dict["map"].append(map_by_game_id.get(id, "unknown"))
                    performance_dict["source_url"].append(basic_match_info["source_url"])

    return performance_dict


def get_team_economy(url, basic_match_info):
    """extract the team economy

    Args:
        url (str): vlr match url
        basic_match_info (dict): basic match info dict. Defaults to None.
        """
    economy_dict = {
        "team_a": [],
        "team_b": [],
        "team_a_economy": [],
        "team_b_economy": [],
        "round": [],
        "team_a_bank": [],
        "team_b_bank": [],
        "map": [],
        "date": [],
        "source_url": [],
        "event": [],
    }
    economy_page = url + "/?game=all&tab=economy"

    soup = soup_open(url)
    soup_economy = soup_open(economy_page)

    get_games_id = soup_economy.find_all("div", {"class": "vm-stats-game"})
    game_ids = [
        div.get("data-game-id") for div in get_games_id if div.has_attr("data-game-id")
    ]

    map_dict = {}

    map_nav_items = soup.select(".vm-stats-gamesnav-item.js-map-switch")

    for item in map_nav_items:
        game_id = item.get("data-game-id")
        map_name = item.get_text(strip=True)[1:]  # Remueve el símbolo inicial como 🗺️

        if game_id:  # Filtramos los que tienen ID válido
            map_dict[game_id] = map_name

    event = basic_match_info["event"]
    source_url = basic_match_info["source_url"]
    date = basic_match_info["date"]

    for value, id in enumerate(game_ids[: len(map_dict) - 1]):

        div = soup_economy.find("div", {"class": "vm-stats-game", "data-game-id": id})
        test_div = div.find_all("tr")[1:]

        teams = []
        round = 0

        for fila in test_div[1:]:
            celdas = fila.find_all("td")
            for celda in celdas:
                rnd_divs = celda.find_all("div", class_="rnd-sq")
                if len(rnd_divs) < 2:
                    continue  # saltamos si no hay info de ambas mitades

                # Extraemos los valores del atributo title
                try:
                    econ_a = rnd_divs[0].get("title", "").strip()
                    econ_b = rnd_divs[1].get("title", "").strip()
                except:
                    econ_a, econ_b = "", ""

                economy_dict["team_a_economy"].append(econ_a)
                economy_dict["team_b_economy"].append(econ_b)

            if len(teams) < 2:
                teams.append(
                    celdas[0].find_all("div", {"class": "team"})[0].get_text(strip=True)
                )
            for bank in celdas:
                team_bank = bank.find_all("div", {"class": "bank"})
                if len(team_bank) > 0:
                    round += 1
                    economy_dict["team_a"].append(teams[1])
                    economy_dict["team_b"].append(teams[0])
                    economy_dict["team_a_bank"].append(
                        team_bank[0].get_text(strip=True)
                    )
                    economy_dict["team_b_bank"].append(
                        team_bank[1].get_text(strip=True)
                    )
                    economy_dict["round"].append(round)
                    economy_dict["map"].append(map_dict.get(id, "Unknown"))
                    economy_dict["date"].append(date)
                    economy_dict["source_url"].append(source_url)
                    economy_dict["event"].append(event)

    return [economy_dict]


# Round logs (tab=logs): compras por jugador y eventos (kills / plant / defuse) por ronda
SHIELD_NAMES = {"Heavy armor": "Heavy", "Light armor": "Light", "Regen Shield": "Regen"}


def parse_credits(text):
    """"−2,400" / "1,050" -> 2400 / 1050 (el gasto viene con signo menos unicode)"""
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def played_game_ids(soup):
    """{game_id: mapa} de los mapas jugados segun el nav del match (sin "all" ni los mod-disabled)"""
    games = {}
    for item in soup.select(".vm-stats-gamesnav-item.js-map-switch"):
        game_id = item.get("data-game-id")
        if not game_id or game_id == "all" or "mod-disabled" in item.get("class", []):
            continue
        # el texto viene como "1Abyss": sacamos el numero de orden
        games[game_id] = re.sub(r"^\d+", "", item.get_text(strip=True))
    return games


def get_round_logs(soup, url, basic_match_info):
    """extract the buy phase and the events of every round from the vlr logs tab

    La pagina ?game=<id>&tab=logs trae todas las rondas de ese mapa (div.lg-round), asi
    que es un request por mapa jugado. Cada ronda tiene las 5 filas de compra por equipo
    (lg-mir-row) y un JSON en div.lg-map[data-map] con los eventos; el feed (lg-row,
    alineado por data-ev) agrega el arma de cada kill y el sitio del plant/defuse.

    Args:
        soup (bs4.BeautifulSoup): pagina principal del match (para el nav de mapas)
        url (str): vlr match url
        basic_match_info (dict): basic match info dict

    Returns:
        tuple: (buy_dict, events_dict); listas vacias si el match no tiene logs
    """
    buy_dict = {
        "team_a": [],
        "team_b": [],
        "map": [],
        "map_id_vlr": [],
        "round": [],
        "team": [],
        "side": [],
        "slot": [],
        "player": [],
        "agent": [],
        "shield": [],
        "weapon": [],
        "spent": [],
        "bank": [],
        "date": [],
        "event": [],
        "source_url": [],
    }
    events_dict = {
        "map": [],
        "map_id_vlr": [],
        "round": [],
        "ev_index": [],
        "clock": [],
        "type": [],
        "by_player": [],
        "by_team": [],
        "victim": [],
        "victim_team": [],
        "weapon": [],
        "site": [],
        "pos_x": [],
        "pos_y": [],
        "from_x": [],
        "from_y": [],
        "date": [],
        "event": [],
        "source_url": [],
    }

    date = basic_match_info["date"]
    event = basic_match_info["event"]
    source_url = basic_match_info["source_url"]

    for game_id, map_name in played_game_ids(soup).items():
        soup_logs = soup_open(url + f"/?game={game_id}&tab=logs")
        game_div = soup_logs.find("div", {"class": "vm-stats-game", "data-game-id": game_id})
        if game_div is None:
            continue

        for round_div in game_div.find_all("div", class_="lg-round"):
            round_number = int(round_div["data-round"])

            # tag de t1 / t2 (los ids de equipo del JSON de eventos)
            band_tags = {}
            for band_team in round_div.select(".lg-band .lg-band-team"):
                tag = band_team.find(class_="lg-band-tag").get_text(strip=True)
                band_tags[1 if "mod-t1" in band_team["class"] else 2] = tag

            # compras
            for team_div in round_div.find_all("div", class_="lg-mir-team"):
                side = "atk" if "mod-atk" in team_div["class"] else "def"
                for slot, row in enumerate(team_div.find_all("div", class_="lg-mir-row"), 1):
                    agent_img = row.find("img", class_="lg-agent")
                    agent = re.search(r"\(([^)]+)\)\s*$", agent_img.get("title", "")) if agent_img else None
                    shield_img = row.find("img", class_="lg-kit-shield")
                    gun_img = row.find("img", class_="lg-kit-gun")

                    buy_dict["team_a"].append(basic_match_info["team_a_tricode"])
                    buy_dict["team_b"].append(basic_match_info["team_b_tricode"])
                    buy_dict["map"].append(map_name)
                    buy_dict["map_id_vlr"].append(game_id)
                    buy_dict["round"].append(round_number)
                    buy_dict["team"].append(row.find(class_="lg-mir-tag").get_text(strip=True))
                    buy_dict["side"].append(side)
                    buy_dict["slot"].append(slot)
                    buy_dict["player"].append(row.find(class_="lg-mir-name").get_text(strip=True))
                    buy_dict["agent"].append(agent.group(1) if agent else None)
                    buy_dict["shield"].append(
                        SHIELD_NAMES.get(shield_img.get("title"), shield_img.get("title")) if shield_img else "No armor"
                    )
                    buy_dict["weapon"].append(gun_img.get("title") if gun_img else None)
                    spent = row.find(class_="lg-kit-spent")
                    bank = row.find(class_="lg-mir-left")
                    buy_dict["spent"].append(parse_credits(spent.get_text() if spent else ""))
                    buy_dict["bank"].append(parse_credits(bank.get_text() if bank else ""))
                    buy_dict["date"].append(date)
                    buy_dict["event"].append(event)
                    buy_dict["source_url"].append(source_url)

            # eventos
            map_div = round_div.find("div", class_="lg-map")
            if map_div is None or not map_div.get("data-map"):
                continue
            data = json.loads(map_div["data-map"])
            players = data.get("players", {})
            feed_rows = {
                int(row["data-ev"]): row for row in round_div.select(".lg-feed .lg-row[data-ev]")
            }

            def player_info(player_id):
                info = players.get(str(player_id))
                if info is None:
                    return None, None
                return info[2], band_tags.get(info[0])

            for index, ev in enumerate(data.get("events", [])):
                feed_row = feed_rows.get(index)
                source = feed_row.find(class_="lg-source") if feed_row else None
                site = feed_row.find(class_="lg-site-text") if feed_row else None
                by_player, by_team = player_info(ev.get("by"))
                victim, victim_team = player_info(ev.get("vid")) if "vid" in ev else (None, None)
                # pos: donde ocurre el evento (la victima en una kill, el spike en plant/defuse);
                # from: desde donde disparo el killer (solo kills). Coordenadas del svg del mapa
                pos = ev.get("pos") or [None, None]
                origin = ev.get("from") or [None, None]

                events_dict["map"].append(map_name)
                events_dict["map_id_vlr"].append(game_id)
                events_dict["round"].append(round_number)
                events_dict["ev_index"].append(index)
                events_dict["clock"].append(ev.get("t"))
                events_dict["type"].append(ev.get("type"))
                events_dict["by_player"].append(by_player)
                events_dict["by_team"].append(by_team)
                events_dict["victim"].append(victim)
                events_dict["victim_team"].append(victim_team)
                events_dict["weapon"].append(source.get("title") if source else None)
                events_dict["site"].append(site.get_text(strip=True) if site else None)
                events_dict["pos_x"].append(pos[0])
                events_dict["pos_y"].append(pos[1])
                events_dict["from_x"].append(origin[0])
                events_dict["from_y"].append(origin[1])
                events_dict["date"].append(date)
                events_dict["event"].append(event)
                events_dict["source_url"].append(source_url)

    return buy_dict, events_dict


def get_player_stats(soup, basic_match_info):
    """extract player stats from a vlr match and return a dict

    Parses the div-based overview layout (ovw-row / ovw-cell with data-col
    attributes) that vlr.gg uses since July 2026. Each vm-stats-game block
    holds its own rows, so map/team assignment comes straight from the block.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup object with the HTML info
        basic_match_info (dict, optional): basic match info dict. Defaults to None.

    Returns:
        dict: player stats dict
    """
    player_stats = {
        "team": [],
        "player": [],
        "agent": [],
        "ratingBoth": [],
        "ratingT": [],
        "rating-ct": [],
        "acsBoth": [],
        "acsT": [],
        "acsCT": [],
        "killsBoth": [],
        "killsT": [],
        "killsCT": [],
        "deadBoth": [],
        "deadT": [],
        "deadCT": [],
        "assistsBoth": [],
        "assistsT": [],
        "assistsCT": [],
        "k-dBoth": [],
        "k-dT": [],
        "k-dCT": [],
        "kastBoth": [],
        "kastT": [],
        "kastCT": [],
        "adrBoth": [],
        "adrT": [],
        "adrCT": [],
        "hsBoth": [],
        "hsT": [],
        "hsCT": [],
        "fkBoth": [],
        "fkT": [],
        "fkCT": [],
        "fdBoth": [],
        "fdT": [],
        "fdCT": [],
        "fk-fdBoth": [],
        "fk-fdT": [],
        "fk-fdCT": [],
        "map": [],
        "map_id_vlr": [],
        "map_duration": [],
        "date": [],
        "source_url": [],
        "event": [],
    }

    # data-col of each ovw-cell -> base name of the player_stats keys
    # (kills/deaths/assists live inside the mod-kda cell as ovw-kda-stat spans)
    col_to_key = {
        "rating2": ("ratingBoth", "ratingT", "rating-ct"),
        "acs": ("acsBoth", "acsT", "acsCT"),
        "kills": ("killsBoth", "killsT", "killsCT"),
        "deaths": ("deadBoth", "deadT", "deadCT"),
        "assists": ("assistsBoth", "assistsT", "assistsCT"),
        "kd-diff": ("k-dBoth", "k-dT", "k-dCT"),
        "kast": ("kastBoth", "kastT", "kastCT"),
        "adr": ("adrBoth", "adrT", "adrCT"),
        "hsp": ("hsBoth", "hsT", "hsCT"),
        "fb": ("fkBoth", "fkT", "fkCT"),
        "fd": ("fdBoth", "fdT", "fdCT"),
        "fk-diff": ("fk-fdBoth", "fk-fdT", "fk-fdCT"),
    }

    def parse_stat_value(text):
        text = text.strip().replace("\xa0", "0")
        if text == "":
            return 0.0
        if text[-1] == "%":
            return float(text[:-1].replace("\xa0", "0")) / 100
        return float(text)

    def side_values(container):
        values = []
        for side in ("mod-both", "mod-t", "mod-ct"):
            span = container.find("span", class_=side)
            values.append(parse_stat_value(span.get_text()) if span else 0.0)
        return values

    date = basic_match_info["date"]
    event = basic_match_info["event"]
    source_url = basic_match_info["source_url"]

    vm_stats = soup.find_all("div", {"class": "vm-stats-game"})

    for game in vm_stats:
        game_id = game.get("data-game-id")

        map_div = game.find("div", class_="map")
        if map_div is not None:
            map_name = parse_map_name(map_div) or "unknown"
            duration_div = map_div.find("div", class_="map-duration")
            map_duration = duration_div.get_text(strip=True) if duration_div else "unknown"
        else:
            # aggregate block over all maps
            map_name = "all"
            map_duration = "all"

        for row in game.find_all("div", class_="ovw-row"):
            name_div = row.find("div", class_="ovw-player-name")
            if name_div is None:
                continue  # header row (ovw-th cells)

            team_div = row.find("div", class_="ovw-player-tag")
            agent_img = row.select_one(".ovw-agents img")

            player_stats["player"].append(name_div.get_text(strip=True))
            player_stats["team"].append(team_div.get_text(strip=True) if team_div else "")
            player_stats["agent"].append(agent_img.get("title") if agent_img else None)

            for col, keys in col_to_key.items():
                container = row.find(attrs={"data-col": col})
                if container is not None:
                    both, t, ct = side_values(container)
                else:
                    both, t, ct = 0.0, 0.0, 0.0
                player_stats[keys[0]].append(both)
                player_stats[keys[1]].append(t)
                player_stats[keys[2]].append(ct)

            player_stats["map"].append(map_name)
            player_stats["map_id_vlr"].append(game_id)
            player_stats["map_duration"].append(map_duration)
            player_stats["date"].append(date)
            player_stats["source_url"].append(source_url)
            player_stats["event"].append(event)

    return player_stats
