-- Staging de players: un jugador de vlr por fila. Nick y equipo son los de su partido mas reciente.
-- legacy_player_id = '<tag>_<nick>', la identidad vieja que todavia usa rktdata: no es unica.

with source as (

    select * from {{ source('vlr', 'players') }}

)

select
    player_id_vlr,
    player          as player_name,
    team_id_vlr,
    team_id         as team_tag,
    player_id       as legacy_player_id
from source
