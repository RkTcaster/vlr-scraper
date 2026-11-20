-- Staging de match_id: una serie de vlr por fila.

with source as (

    select * from {{ source('vlr', 'match_id') }}

),

renamed as (

    select
        series_id                   as vlr_series_id,
        reg_id                      as region_id,
        tour_id                     as tournament_id,
        match_format                -- full / reduced

    from source

)

select * from renamed
