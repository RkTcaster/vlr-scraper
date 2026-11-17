"""Listas de referencia mantenidas a mano.

Mapas y agentes nuevos se agregan aca; si faltan, sus filas no reciben id/imagen.
"""

# Regiones. El orden importa: reg_2 = china se usa como filtro especial.
region_name = ["americas", "emea", "china", "pacific", "global"]
region_id = ["reg_0", "reg_1", "reg_2", "reg_3", "reg_4"]

# Texto exacto del chip de subregion en rviewer (handoff/VLR_SCRAPER_TOURNAMENT_HIERARCHY.md),
# por la parte del tour_id entre "_-_" y "_[open|closed_]qualifier". Una subregion que no este
# aca sale en Title Case con un warning: agregarla y avisar a rviewer.
subregion_names = {
    "north america": "North America",
    "latam north": "LATAM North",
    "latam south": "LATAM South",
    "europe": "Europe",
    "mena": "MENA",  # 2026-11-09, avisado a rviewer (handoff/RVIEWER_SUBREGIONES_NUEVAS.md)
    "brazil": "Brazil",
    "türkiye": "Türkiye",  # 2026-11-11, avisado a rviewer (handoff/RVIEWER_SUBREGIONES_NUEVAS.md)
    # 2026-11-17, Pacific Kickoff 2027 (Title Case tal cual sale del nombre; a confirmar por rviewer,
    # handoff/RVIEWER_SUBREGIONES_PACIFIC_Y_EQUIPOS.md). "Thailand Qualifier 1" -> "thailand"
    "korea": "Korea",
    "thailand": "Thailand",
    "indonesia": "Indonesia",
    "southeast asia": "Southeast Asia",
    "south asia": "South Asia",
    "oceania": "Oceania",
    "vietnam": "Vietnam",
}

# Subregion fija de un equipo (team_id_vlr -> texto del chip), para los que no salen de un
# qualifier (equipos de partner). Tiene prioridad sobre la subregion calculada en build_teams.
# Sembrado el 2026-11-17 con lo que rviewer habia cargado a mano en Supabase teams.subregion:
# desde ahi table_teams.csv es el dueño de la columna y el upsert pisa lo editado a mano.
team_subregions = {
    "15072": "Brazil",  # 2Game Esports
    "23141": "Brazil",  # Fluxo W7M
    "2406": "Brazil",  # FURIA
    "6961": "Brazil",  # LOUD
    "7386": "Brazil",  # MIBR
    "20603": "China",  # A Team
    "1119": "China",  # All Gamers
    "12010": "China",  # Bilibili Gaming
    "11981": "China",  # Dragon Ranger Gaming
    "1120": "China",  # EDward Gaming
    "11328": "China",  # FunPlus Phoenix
    "13576": "China",  # JD Gaming
    "12784": "China",  # KeepBest Gaming
    "12064": "China",  # Nova Esports
    "14137": "China",  # Titan Esports Club
    "12685": "China",  # Trace Esports
    "731": "China",  # TYLOO
    "13790": "China",  # Wolves Esports
    "13581": "China",  # Xi Lai Gaming
    "14478": "Europe",  # Eintracht Frankfurt
    "876": "Europe",  # Enterprise Esports
    "2593": "Europe",  # FNATIC
    "12694": "Europe",  # Gentle Mates
    "14419": "Europe",  # GIANTX
    "11232": "Europe",  # Joblife
    "8877": "Europe",  # Karmine Corp
    "4915": "Europe",  # Natus Vincere
    "3478": "Europe",  # PCIFIC Esports
    "1001": "Europe",  # Team Heretics
    "474": "Europe",  # Team Liquid
    "2059": "Europe",  # Team Vitality
    "18019": "Europe",  # ULF Esports
    "11229": "Japan",  # VARREL
    "5448": "Japan",  # ZETA DIVISION
    "17": "Korea",  # Gen.G
    "8185": "Korea",  # KIWOOM DRX
    "11060": "Korea",  # Nongshim RedForce
    "14": "Korea",  # T1
    "22142": "LATAM South",  # BESTIA
    "2355": "LATAM South",  # KRÜ Esports
    "2359": "LATAM South",  # LEVIATÁN
    "120": "North America",  # 100 Thieves
    "188": "North America",  # Cloud9
    "427": "North America",  # ENVY
    "5248": "North America",  # Evil Geniuses
    "11058": "North America",  # G2 Esports
    "11001": "North America",  # M80
    "1034": "North America",  # NRG
    "2": "North America",  # Sentinels
    "278": "SEA",  # DetonatioN FocusMe
    "4050": "SEA",  # FULL SENSE
    "918": "SEA",  # Global Esports
    "19189": "SEA",  # ONSIDE GAMING
    "624": "SEA",  # Paper Rex
    "18299": "SEA",  # QT DIG∞
    "878": "SEA",  # Rex Regum Qeon
    "623": "SEA",  # Sharper Esports
    "6199": "SEA",  # Team Secret
    "17167": "SEA",  # Xipto Esports
    "397": "Türkiye",  # BBL Esports
    "6392": "Türkiye",  # Eternal Fire
    "20085": "Türkiye",  # Fire Flux Esports
    "1184": "Türkiye",  # FUT Esports
}

# table with the maps force the maps I should add new maps manually
map_info = {
    "map": [
        "Haven",
        "Pearl",
        "Abyss",
        "Split",
        "Corrode",
        "Breeze",
        "Bind",
        "Ascent",
        "Fracture",
        "Icebox",
        "Lotus",
        "Sunset",
        "Summit",
    ], "image_path": []
}
map_info["image_path"] = [f"maps/{nombre.lower()}.png" for nombre in map_info["map"]]

# Agent names and urls
agent_path_name = [
    "astra.png",
    "breach.png",
    "brimstone.png",
    "chamber.png",
    "clove.png",
    "cypher.png",
    "deadlock.png",
    "fade.png",
    "gekko.png",
    "harbor.png",
    "hush.png",
    "iso.png",
    "jett.png",
    "kayo.png",
    "killjoy.png",
    "miks.png",
    "neon.png",
    "omen.png",
    "phoenix.png",
    "raze.png",
    "reyna.png",
    "sage.png",
    "skye.png",
    "sova.png",
    "tejo.png",
    "veto.png",
    "viper.png",
    "vyse.png",
    "waylay.png",
    "yoru.png",
]

# Tricodes que vlr renombro despues de que scrapeamos round_detail: tag nuevo -> el que quedo en
# round_info (que es el que forma team_map_round_id, table_teams y table_players). Sin esto las
# solapas que se bajan ahora traen el tag nuevo y no joinean con las rondas viejas: el side y las
# kills por equipo salen mal y el conteo de vivos de round_situations pierde las muertes.
# Agregar a mano cuando aparezca un tag desconocido en los warnings de round_buy / round_events.
team_aliases = {
    "KRX": "DRX",  # DRX -> KRX, visto en vct_2026_pacific_kickoff (6 series)
}
