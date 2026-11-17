-- Generado por scripts/relevant_teams.py desde relevant_teams.json. No editar a mano.
-- VCT 2027 Kickoffs (Americas / EMEA): clasificados de las open qualifiers a las closed
begin;

update teams
set relevant = false;

update teams
set relevant = true
where team_id_vlr in (
  -- LATAM SOUTH
  '24258',  -- EL L EL LEGADO
  '24257',  -- TRAM TRAMITE
  '24246',  -- ARG. ARG.MIX
  '24320',  -- FRAC fracasados ny
  '25222',  -- MALA MALAJUNTA
  -- LATAM NORTH
  '12889',  -- SQR Squirtle Rangers
  '21459',  -- STA STREAMER ARENA
  '25292',  -- 505 505
  '25283',  -- OLD Old School Krew
  -- BRAZIL
  '24636',  -- SOLI Team Solid
  '24496',  -- BRA2002 BRASIL2002
  '24401',  -- TB3 TIME DO B3M
  '23180',  -- ARAS Arashi
  '24553',  -- MAFIA Mafiosos
  '16854',  -- PDC Piranhas do Caribe
  '12642',  -- ARRA ARRANCA DREAMS
  '24478',  -- SV SÓ TEM VELHO
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

-- control: 39 filas esperadas (44 ids en la lista)
select team_id_vlr, team_id, name from teams where relevant = true order by team_id;
