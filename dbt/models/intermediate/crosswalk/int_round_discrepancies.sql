-- Las rondas emparejadas en las que GRID y vlr no dicen lo mismo, con contexto para revisarlas a mano:
-- ganador distinto, forma de ganar distinta, o ronda que esta en una sola fuente.
-- El test assert_grid_vlr_rounds_agree (warn) cuenta estas filas.

select
    match_status,
    case
        when match_status <> 'mismatch'                     then match_status
        when not winner_matches and not win_con_matches     then 'winner_and_win_con'
        when not winner_matches                             then 'winner'
        when not win_con_matches                            then 'win_con'
        else 'unknown_in_grid'      -- winType 'unknown' o ronda sin ganador en GRID: comparacion con NULL
    end                             as discrepancy,
    grid_series_id,
    vlr_series_id,
    map_name,
    round_number,
    grid_winner_id_vlr,
    vlr_winner_id_vlr,
    grid_win_type,
    grid_win_con,
    vlr_win_con,
    has_player_stats,
    round_pair_id,
    team_map_round_id

from {{ ref('int_round_crosswalk') }}
where match_status <> 'match'
