-- Una fila por equipo y serie del catalogo de Central Data. De aca sale el tag (nameShortened) y el id de Riot
-- del equipo, que Series State no trae. El nombre de aca NO se usa: Central Data rompe los caracteres no ASCII
-- (para el nombre esta stg_grid__series_teams).

with source as (

    select * from {{ source('grid', 'series_catalog') }}

),

teams as (

    select id as grid_series_id, unnest(teams) as team from source

),

renamed as (

    select
        grid_series_id || '-' || team.baseInfo.id           as series_team_id,
        grid_series_id,
        team.baseInfo.id                                    as grid_team_id,
        nullif(trim(team.baseInfo.nameShortened), '')       as team_tag,          -- viene con espacios: " VIL"
        list_filter(team.baseInfo.externalLinks, lambda l: l.dataProvider.name = 'VALORANT')[1].externalEntity.id
                                                            as riot_team_id,
        team.scoreAdvantage                                 as score_advantage

    from teams

)

select * from renamed
