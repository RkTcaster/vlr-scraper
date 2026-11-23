-- Staging de teams: un modelo por source, sin joins ni logica de negocio.
-- Solo renombra, tipa y ordena columnas; todo lo demas del proyecto lee de aca y no del csv.

with source as (

    select * from {{ source('vlr', 'teams') }}

),

renamed as (

    select
        team_id_vlr,                -- id de vlr (/team/<id>/) o tbd_<TAG>: la PK
        team_id   as team_tag,      -- tricode; se repite entre equipos sin relacion
        name      as team_name,
        team_path as logo_path,
        nullif(subregion, '') as subregion  -- lookups.team_subregions o el ultimo qualifier jugado

    from source

)

select * from renamed
