-- Una fila por equipo y serie: resultado de la serie. Sale del Series State (no del catalogo) porque ahi los
-- nombres llegan bien ("VISA KRU Blaze" con dieresis; en Central Data viene roto).

with base as (

    select * from {{ ref('base_grid__series_state') }}

),

-- unnest() en el SELECT: una fila por elemento de la lista, repitiendo las demas columnas (series_id)
teams as (

    select
        series_id,
        unnest(state.teams) as team
    from base

),

renamed as (

    select
        series_id || '-' || team.id                         as series_team_id,
        series_id                                           as grid_series_id,
        team.id                                             as grid_team_id,
        team.name                                           as team_name,
        team.score                                          as maps_won,
        team.won                                            as won_series

    from teams

)

select * from renamed
