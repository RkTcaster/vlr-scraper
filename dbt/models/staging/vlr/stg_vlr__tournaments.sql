-- Staging de tournament. Aca aparece el primer cast: del csv todo llega como texto.

with source as (

    select * from {{ source('vlr', 'tournament') }}

),

renamed as (

    select
        tour_id       as tournament_id,
        event         as tournament_name,
        reg_id        as region_id,
        cast(year as integer) as season_year,
        stage,
        subregion,                  -- solo en qualifiers; vacio = null
        match_format                -- full / reduced / mixed

    from source

)

select * from renamed
