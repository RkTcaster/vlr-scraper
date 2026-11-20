-- Una fila por accion del veto de mapas (nivel serie). GRID lo trae en ~18% de las series: VCT Americas y EMEA,
-- Masters y Champions (~90% de esas), casi nada en GC y MENA Pulse, y nada en Pacific, CN ni Challengers.
-- Detalle por torneo en analyses/grid_draft_coverage.sql.
--
-- Orden tipico de un Bo3: ban, ban, pick (mapa), pick (lado del rival), pick, pick (lado), ..., decider.
--   action_type   ban / pick
--   drafter_type  team (el equipo que elige) / series (el decider, lo elige "la serie")
--   draftable_type map / side (attacker / defender)

with base as (

    select * from {{ ref('base_grid__series_state') }}

),

actions as (

    select
        series_id,
        unnest(state.draftActions) as action
    from base

),

renamed as (

    select
        series_id || '-' || action.sequenceNumber           as draft_action_id,
        series_id                                           as grid_series_id,
        cast(action.sequenceNumber as integer)              as action_number,     -- viene como texto
        action.type                                         as action_type,
        action.drafter.type                                 as drafter_type,
        action.drafter.id                                   as drafter_id,        -- grid_team_id, o el id de la serie
        case when action.drafter.type = 'team'
             then series_id || '-' || action.drafter.id end as drafter_series_team_id,
        action.draftable.type                               as draftable_type,
        action.draftable.name                               as draftable_name     -- mapa o lado

    from actions

)

select * from renamed
