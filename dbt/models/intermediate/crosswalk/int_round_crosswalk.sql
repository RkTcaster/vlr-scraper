-- Ronda de GRID <-> ronda de vlr, dentro de un mapa emparejado, por numero de ronda. Compara lo que las dos
-- fuentes dicen de cada ronda: ganador, como se gano y lado del ganador.
--
-- full outer join: una ronda que esta en una sola fuente aparece igual (match_status missing_in_grid /
-- missing_in_vlr), en vez de perderse en silencio.

with maps as (

    select grid_game_id, vlr_map_id, grid_series_id, vlr_series_id, map_name, has_player_stats
    from {{ ref('int_map_crosswalk') }}

),

grid_rounds as (

    select
        m.grid_game_id,
        r.round_number,
        r.grid_round_id,
        x.team_id_vlr                       as winner_id_vlr,     -- el ganador de GRID traducido a id de vlr
        r.winner_side,
        -- winType de GRID al vocabulario de vlr (winCon)
        case r.win_type
            when 'opponentEliminated' then 'elim'
            when 'bombExploded'       then 'boom'
            when 'bombDefused'        then 'defus'
            when 'timeExpired'        then 'tim'
        end                                 as win_con,
        r.win_type                          as grid_win_type
    from maps as m
    join {{ ref('stg_grid__rounds') }} as r using (grid_game_id)
    left join {{ ref('int_team_crosswalk') }} as x on x.grid_team_id = r.winner_grid_team_id

),

vlr_rounds as (

    select
        m.grid_game_id,
        r.round_number,
        r.team_map_round_id,
        case when r.team_a_won then r.team_a_id_vlr else r.team_b_id_vlr end   as winner_id_vlr,
        case
            when r.team_a_won then r.team_a_side
            when r.team_a_side = 'attacker' then 'defender'
            else 'attacker'
        end                                                                     as winner_side,
        r.win_con
    from maps as m
    join {{ ref('stg_vlr__rounds') }} as r using (vlr_map_id)

),

joined as (

    select
        coalesce(g.grid_game_id, v.grid_game_id)    as grid_game_id,
        coalesce(g.round_number, v.round_number)    as round_number,
        g.grid_round_id,
        v.team_map_round_id,
        g.winner_id_vlr                             as grid_winner_id_vlr,
        v.winner_id_vlr                             as vlr_winner_id_vlr,
        g.winner_side                               as grid_winner_side,
        v.winner_side                               as vlr_winner_side,
        g.win_con                                   as grid_win_con,
        g.grid_win_type,
        v.win_con                                   as vlr_win_con
    from grid_rounds as g
    full outer join vlr_rounds as v
      on g.grid_game_id = v.grid_game_id
     and g.round_number = v.round_number

)

select
    j.grid_game_id || '-' || j.round_number                     as round_pair_id,
    m.grid_series_id,
    m.vlr_series_id,
    m.vlr_map_id,
    m.map_name,
    m.has_player_stats,
    j.*,
    j.grid_winner_id_vlr = j.vlr_winner_id_vlr                   as winner_matches,
    j.grid_win_con = j.vlr_win_con                               as win_con_matches,
    j.grid_winner_side = j.vlr_winner_side                       as winner_side_matches,
    case
        when j.grid_round_id is null        then 'missing_in_grid'
        when j.team_map_round_id is null    then 'missing_in_vlr'
        when j.grid_winner_id_vlr = j.vlr_winner_id_vlr
         and j.grid_win_con = j.vlr_win_con then 'match'
        else 'mismatch'
    end                                                          as match_status

from joined as j
join maps as m using (grid_game_id)
