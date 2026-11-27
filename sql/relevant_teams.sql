-- Generado por scripts/relevant_teams.py desde relevant_teams.json. No editar a mano.
-- VCT 2027 Kickoffs (Americas / EMEA): equipos de las closed qualifiers (Americas: todos los de los qualifier playoffs)
begin;

update teams
set relevant = false;

update teams
set relevant = true
where team_id_vlr in (
  -- LATAM SOUTH
  '24258',  -- EL L EL LEGADO
  '20209',  -- UW University War
  '24246',  -- ARG. ARG.MIX
  '367',  -- 9ZG 9z Globant
  -- LATAM NORTH
  '23777',  -- LEON LEONS
  '17252',  -- FUE FUEGO
  '2131',  -- CHV Chivas Esports
  '10376',  -- BBB Contra
  -- BRAZIL
  '24478',  -- SV SÓ TEM VELHO
  '15072',  -- 2G 2Game Esports
  '19265',  -- TSS Team Solid
  '23141',  -- FX Fluxo W7M
  '20741',  -- NXT Next
  '18622',  -- ELV ELEVATE
  '24496',  -- BRA2002 BRASIL2002
  '24553',  -- MAFIA Mafiosos
  -- NA QUALIFIER PLAYOFFS
  '188',  -- C9 Cloud9
  '427',  -- ENVY ENVY
  '9353',  -- SRB Shopify Rebellion Black
  '5038',  -- YFP YFP
  '23892',  -- OAF Oafs
  '23815',  -- FAKE counterfeit
  '23975',  -- WC Wildcard
  '6985',  -- QOR QoR
  -- EUROPE
  '4616',  -- UCAM UCAM Esports Club
  '14478',  -- SGE Eintracht Frankfurt
  '17945',  -- MIR MIR
  '11232',  -- JL Joblife
  '21715',  -- NVJ Natus Vincere Junior
  '7967',  -- MDR Mandatory
  '14419',  -- GX GIANTX
  '876',  -- EP Enterprise Esports
  '23727',  -- AURA Aurora Gaming
  '18494',  -- F9 F9 EICAR
  '23693',  -- MPMT xXxMasterProMegaTeamxXx
  '17177',  -- PXL Pixel Lumina
  '5214',  -- CGN CGN Esports
  '14461',  -- BAR Barça eSports
  '19391',  -- WIP WIP Esports
  '18025',  -- MSA La Masia
  -- MENA
  '24602',  -- NO O No Org No Problem
  '23069'  -- MIX Mix My Miks
);

commit;

-- control: 42 filas esperadas (42 ids en la lista)
select team_id_vlr, team_id, name from teams where relevant = true order by team_id;
