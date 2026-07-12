"""Listas de referencia mantenidas a mano (csv_process.ipynb celdas 4, 15 y 18).

Mapas y agentes nuevos se agregan aca; si faltan, sus filas no reciben id/imagen.
"""

# Regiones (celda 4). El orden importa: reg_2 = china se usa como filtro especial.
region_name = ["americas", "emea", "china", "pacific", "global"]
region_id = ["reg_0", "reg_1", "reg_2", "reg_3", "reg_4"]

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
