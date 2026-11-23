-- Generado por scripts/relevant_teams.py desde relevant_teams.json. No editar a mano.
-- VCT 2027 Kickoffs (Americas / EMEA): equipos de las closed qualifiers (Americas: todos los de los qualifier playoffs)
begin;

update teams
set relevant = false;

update teams
set relevant = true
where team_id_vlr in (
  -- LATAM SOUTH
  '367',  -- 9ZG 9z Globant
  '7511',  -- KRUB KRÜ BLAZE
  '20209',  -- UW University War
  '24257',  -- TRAM TRAMITE
  '24258',  -- EL L EL LEGADO
  '24246',  -- ARG. ARG.MIX
  '25222',  -- MALA MALAJUNTA
  '24320',  -- FRAC fracasados ny
  -- LATAM NORTH
  '10376',  -- BBB Contra
  '23777',  -- LEON LEONS
  '17252',  -- FUE FUEGO
  '2131',  -- CHV Chivas Esports
  '21459',  -- STA STREAMER ARENA
  '12889',  -- SQR Squirtle Rangers
  '25292',  -- 505 505
  '11720',  -- OSK Old School Kr3w
  -- BRAZIL
  '23141',  -- FX Fluxo W7M
  '15072',  -- 2G 2Game Esports
  '19265',  -- TSS Team Solid
  '20741',  -- NXT Next
  '18622',  -- ELV ELEVATE
  '23778',  -- MANT Manticore
  '24496',  -- BRA2002 BRASIL2002
  '25330',  -- GANG GANGUE
  '24553',  -- MAFIA Mafiosos
  '24401',  -- TB3 TIME DO B3M
  '23180',  -- ARAS Arashi
  '16854',  -- PDC Piranhas do Caribe
  '24478',  -- SV SÓ TEM VELHO
  '12642',  -- ARRA ARRANCA DREAMS
  '24507',  -- 171 Master Bank
  '25111',  -- 100%MIRA 0 intelecto
  -- NA QUALIFIER PLAYOFFS
  '427',  -- ENVY ENVY
  '188',  -- C9 Cloud9
  '9353',  -- SRB Shopify Rebellion Black
  '6985',  -- QOR QoR
  '21838',  -- FLY FlyQuest
  '14278',  -- SRG Shopify Rebellion Gold
  '5038',  -- YFP YFP
  '13920',  -- SAD SaD Esports
  '23878',  -- MC Masterclass
  '23892',  -- OAF Oafs
  '10448',  -- WU Winthrop University
  '16824',  -- XORA Xora Esports
  '23975',  -- WC Wildcard
  '12900',  -- MU Maryville University
  '23815',  -- FAKE counterfeit
  '23980',  -- YDG Yellow Dragon Gaming
  -- EUROPE
  '4616',  -- UCAM Esports Club (no esta en teams)
  '14478',  -- SGE Eintracht Frankfurt
  '17945',  -- MIR (no esta en teams)
  '11232',  -- JL Joblife
  '21715',  -- Natus Vincere Junior (no esta en teams)
  '7967',  -- Mandatory (no esta en teams)
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

-- control: 62 filas esperadas (66 ids en la lista)
select team_id_vlr, team_id, name from teams where relevant = true order by team_id;
