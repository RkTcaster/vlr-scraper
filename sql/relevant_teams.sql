-- Generado por scripts/relevant_teams.py desde relevant_teams.json. No editar a mano.
-- VCT 2027 Kickoffs (Americas / EMEA): equipos de las closed qualifiers (Americas: todos los de los qualifier playoffs)
begin;

update teams
set relevant = false;

update teams
set relevant = true
where team_id_vlr in (
  -- LATAM SOUTH
  '367',  -- 9z Globant (no esta en teams)
  '7511',  -- KRUB KRÜ BLAZE
  '20209',  -- University War (no esta en teams)
  '24257',  -- TRAM TRAMITE
  '24258',  -- EL L EL LEGADO
  '24246',  -- ARG. ARG.MIX
  '25222',  -- MALA MALAJUNTA
  '24320',  -- FRAC fracasados ny
  -- LATAM NORTH
  '10376',  -- Contra (no esta en teams)
  '23777',  -- LEONS (no esta en teams)
  '17252',  -- FUEGO (no esta en teams)
  '2131',  -- Chivas Esports (no esta en teams)
  '21459',  -- STA STREAMER ARENA
  '12889',  -- SQR Squirtle Rangers
  '25292',  -- 505 505
  '25283',  -- OLD Old School Krew
  -- BRAZIL
  '23141',  -- FX Fluxo W7M
  '15072',  -- 2G 2Game Esports
  '19265',  -- Team Solid (no esta en teams)
  '20741',  -- Next (no esta en teams)
  '18622',  -- ELEVATE (no esta en teams)
  '23778',  -- Manticore (no esta en teams)
  '24496',  -- BRA2002 BRASIL2002
  '25330',  -- GANGUE (no esta en teams)
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
  '9353',  -- Shopify Rebellion Black (no esta en teams)
  '6985',  -- QoR (no esta en teams)
  '21838',  -- FlyQuest (no esta en teams)
  '14278',  -- SRG Shopify Rebellion Gold
  '5038',  -- YFP (no esta en teams)
  '13920',  -- SaD Esports (no esta en teams)
  '23878',  -- MC Masterclass
  '23892',  -- OAF Oafs
  '10448',  -- WU Winthrop University
  '16824',  -- XORA Xora Esports
  '23975',  -- WC Wildcard
  '12900',  -- MU Maryville University
  '23815',  -- FAKE counterfeit
  '23980',  -- YDG Yellow Dragon Gaming
  -- EUROPE
  '23693',  -- MPMT xXxMasterProMegaTeamxXx
  '18494',  -- F9 F9 EICAR
  '23727',  -- AURA Aurora Gaming
  '17177',  -- PXL Pixel Lumina
  '14461',  -- BAR Barça eSports
  '19391',  -- WIP WIP Esports
  '18025',  -- MSA La Masia
  '5214',  -- CGN CGN Esports
  -- MENA
  '24602',  -- NO O No Org No Problem
  '23069'  -- MIX Mix My Miks
);

commit;

-- control: 42 filas esperadas (58 ids en la lista)
select team_id_vlr, team_id, name from teams where relevant = true order by team_id;
