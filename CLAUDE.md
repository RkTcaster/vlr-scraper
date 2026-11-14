# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraping + data-processing pipeline for Valorant esports statistics from [vlr.gg](https://www.vlr.gg).
Output is a star-schema set of CSVs under `tables/` that is upserted into Supabase Postgres tables
(`vlr_pipeline/upload.py`, port of rktdata's `scripts/upload.mjs`: file → table → PK list) and consumed by rktdata.ar.
Credentials come from the environment or, locally, from `.env.local` (`config.load_env_file`, called by the CLI; accepts rktdata's `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` names, never overrides existing env vars; tests disable it via `VLR_ENV_FILE=""`). Upload is **incremental** by default: dimension tables go in full, fact tables only for `series_id`s missing from
Supabase's `match_id` or re-scraped (scrape_log `last_attempt`) after the last all-ok upload; `match_id` is uploaded
last and only for series whose facts succeeded, so failed chunks retry next run. `--full` (CLI, or the `full` input of
"Run workflow") re-uploads everything — needed after changing table-building code or lookups, since existing matches'
rows won't be re-sent otherwise. Every upload run appends one row per table to `csv/upload_log.csv` (mode, rows,
series, failed_rows, status, last error, GitHub run id). Logic exists twice and must be kept in sync: the notebooks (`vlr_scraper.ipynb`,
`csv_process.ipynb`) and the headless package `vlr_pipeline/` (`python -m vlr_pipeline [--log-level X] {scrape,process,upload,all}`;
global flags go before the subcommand).

Production runs in GitHub Actions (`.github/workflows/pipeline.yml`, daily 17:00 UTC; cron always incremental): scrapes the `active` events in
`events.json`, rebuilds `tables/`, uploads to Supabase, and commits only `csv/` back to the repo. `csv/` (including
`csv/scrape_log.csv`) is versioned; `tables/` is gitignored because it is fully regenerated from `csv/` (the package
output was verified byte-identical to the notebook's). The logs-tab csv (`round_buy_`, `round_events_`) are
versioned too since 2026-11-07 (~9 MB compressed in git, ~15-20 MB/year): they were gitignored from 2026-10-20, but
the bot commits `scrape_log.csv` every day anyway, so `has_logs=True` ended up pointing at csv that existed nowhere
(55 matches scraped by Actions lost their logs with the runner). Invariant: `has_logs=True` means the match's
`round_buy_`/`round_events_` rows are in `csv/` **in git** — never ignore those files again without changing that.
`scripts/backfill_all_logs.py --sync-has-logs` rebuilds `has_logs` from the csv on disk, with no requests to vlr, and
`--redo <series_id...>` re-downloads specific matches. GitHub's per-file limit is 100 MB (warns at 50 MB); the largest
logs csv is ~20 MB (`round_buy_` of the 2027 EMEA kickoff qualifier, ~240 matches) — split a file if one ever approaches 50 MB. `.gitattributes` keeps `*.csv` line endings untouched.
Pull before running notebooks locally to avoid conflicts with the bot's commits. `.gitattributes` maps
`csv/**/*.csv` to the `vlr-csv` merge driver (`scripts/merge_csv.py`: 3-way merge per series, local wins when both
sides changed one; must be registered once per clone with `git config`, see `COMMANDS.md`); `--resolve` fixes a
merge that is already conflicted. Comments are frequently in Spanish.

## Environment & running

- `requirements.txt` is a **pip** file (what Actions installs; includes `supabase`, needed only by `upload`):
  `python -m pip install -r requirements.txt`. The old conda spec (Python 3.11, win-64) is `environment.conda.txt`:
  `conda create --name <env> --file environment.conda.txt` (it has no `supabase`; pip-install it on top).
- Core stack: `beautifulsoup4` + `urllib` (scraping), `pandas`/`numpy` (processing), `matplotlib`, `scikit-learn`.
- Run notebooks in Jupyter, or execute headless:
  `jupyter nbconvert --to notebook --execute --inplace vlr_scraper.ipynb`
- Some cells need `PYTHONIOENCODING=utf-8` set (Windows console default mangles non-ASCII team names).

## Notebook roles

- **`vlr_scraper.ipynb`** — the current/canonical scraper. Cells 1–2 define all functions; later cells
  are interactive scratch/testing against a single hardcoded match `url`. Per-tournament CSVs are written to
  `csv/<normalized_tournament>/` with prefixes: `draft_`, `player_stats_`, `player_performance_`,
  `round_detail_`, `team_economy_`, `round_buy_`, `round_events_`, `error_match_`.
- **`csv_process.ipynb`** — consolidation pipeline. `concat_csv_from_different_folders(folder, prefix)` reads
  every per-tournament CSV with a given prefix across `csv/*/`, then builds the dimension/fact tables in
  `tables/table_*.csv` (region, tournament, teams, players, maps, round info, economy, drafts, performance).
  Also exports group `standings.csv` / `h2h.csv` (see the INPUT_CONTRACT cells near the end; contract in `handoff/INPUT_CONTRACT.md`).
- **`Webscraper.ipynb`** — legacy/older version of both the scraper and the downstream pipeline. Uses flat,
  hardcoded filenames (`picks.csv`, `Statsamer1.csv`, `bo5amer1.csv`) and lots of hardcoded region/tournament
  wiring. Prefer `vlr_scraper.ipynb` + `csv_process.ipynb`; keep this only as reference.
- **`round_process.ipynb`** — analysis/exploration of economy buys and round-by-round comeback detection.

## Tests

`python -m pytest` (pytest isn't in requirements.txt; CI installs it in `.github/workflows/tests.yml`, which also runs
after each pipeline run). `test_parsers.py` runs `process_match` offline on gzipped html in `tests/fixtures/html/<series_id>/`
and compares with `tests/fixtures/expected/`; `test_lookups.py` fails when `csv/` has a map/agent missing from
`lookups.py`; `test_primary_keys.py` builds tables from `csv/` and applies `upload.validate_rows` to every PK in
`FILES_TO_UPLOAD`. CLI exit codes: partial scrape failure returns 0 plus a `::warning::` under Actions; 2 is argparse only.

## Architecture conventions (read before editing extractors)

- **`basic_match_info`** — a dict produced by `get_basic_match_info(soup, url)` and threaded through every
  extractor and save function. It is the single source of match context (teams, event, date, source_url, bo).
- **ID scheme** — `series_id` is parsed from the match URL via `re.search(r"vlr\.gg/(\d+)", url)`;
  `map_id = f"{series_id}-{map}"`. Joins across tables rely on these. Region/tournament IDs (`reg_*`, `tour_id`)
  are assigned from the normalized tournament folder name.
- **Player identity (`player_id_vlr`, 2026-11-07)** — a player is vlr's `/player/<id>/`, never the nick: two
  players can share a nick on the same team (785988, LATAM South: two "Splotza" in RADI, 69551 and 50487).
  Only the overview links to the player, so `get_player_stats` writes `player_id_vlr` to `player_stats_`, and
  performance / logs rows get it at table-build time from `player_keys` + `resolve_player_ids` (`tables.py`): by
  `map_id + nick`, and when the nick repeats in that map, by agent (raw `agent` in performance, `by_agent` /
  `victim_agent` in round_events, `agent` in round_buy; agent names are compared lowercased because the overview
  says `Jett` and the logs JSON `jett`). Old performance/events csv have no agent column, which is fine: repeated
  nicks only exist in series scraped after it was added. `table_players` has one row per `player_id_vlr` (PK);
  `player_id = <team>_<nick>` stays as a non-unique legacy column for rktdata. Supabase PKs: `players
  (player_id_vlr)`, `player_stats` / `player_performance (map_id, player_id_vlr)`; logs tables add `*_id_vlr`
  columns (`player_N_team_x_id` in round_buy). Schema change: `sql/player_id_vlr.sql` (empties the three tables,
  then `upload --full`). Some qualifier players have no vlr profile (nick with `mod-tbd`, no link):
  `raw_player_ids` gives them the real id of the same `(team, nick)` if vlr created the profile later and there
  is exactly one, else `tbd_<team>_<nick>`. Nicks are matched with `match_nick` (all whitespace collapsed:
  the overview keeps double spaces, performance does not). Performance/logs rows that still resolve to no id
  are dropped with a warning (`drop_without_player_id`); raw `player_stats_` with an empty id column (scraped
  before it existed) are filled by `scripts/backfill_player_ids.py` (1 overview request per match; run for every
  match on 2026-11-07). Split html text with `parsers.html_words` (ASCII whitespace only), never `str.split()`:
  latin-1-decoded utf-8 contains `\xa0`/`\x85` bytes that `split()` treats as spaces.
- **Team identity (`team_id_vlr`, 2026-11-10, phase 1)** — a team is vlr's `/team/<id>/`, never the tricode:
  20 tags are shared by unrelated teams (`THE` in four qualifiers, `FUR` = FURIA and a Brazil qualifier team) and
  785082 is `FAKE` vs `FAKE`. `get_team_ids` reads the match header (`a.match-header-link` `mod-1`/`mod-2`);
  `round_detail_` stores `team_a_id_vlr`, `team_b_id_vlr`, `team_a_name`, `team_b_name` and `player_stats_`
  stores `team_id_vlr` **by ovw-table position** (first table of each map = team_a), never by tag. At build time
  `team_keys` + `resolve_team_ids` (`tables.py`) give the id by `(series_id, tag)` when the tag is unique in that
  series; anything without an id becomes `tbd_<TAG>` (team without a vlr page, or csv not backfilled:
  `scripts/backfill_team_ids.py`, 1 overview request per series). `table_teams` has one row per `team_id_vlr`
  (Supabase PK) with `team_id` (tag, no longer unique) and `name` from the team's latest match; `players`,
  `player_stats` and `round_info` (`team_a_id_vlr`/`team_b_id_vlr`) carry the id. Schema change:
  `sql/team_id_vlr.sql` (paso A, `upload --full`, paso B restores rviewer's manual `teams.relevant`).
  **Phase 2 (2026-11-13, rviewer's request)** adds id columns *next to* every tag column, without touching
  `team_map_round_id`: `draft` (`team_id_vlr`, `rival_id_vlr`), `team_economy` / `round_buy` / `round_summary`
  (`team_a_id_vlr`, `team_b_id_vlr`, plus `fb_team_id_vlr`), `round_events` (`team_id_vlr`,
  `victim_team_id_vlr`), `player_performance` (`team_id_vlr`), and `tournament_played` whose PK is now
  `(tour_id, team_id_vlr)` (`teamA` = the team's latest tag in that tournament). A player's team comes from
  `player_keys` (`player_team_ids`: overview position, by `map_id + player_id_vlr`), falling back to the tag
  against round_info (`side_team_ids`); events compare teams by id (side, team kill, trades, kills per team), and
  round_buy's `which` uses the player's team, so 785082 works. Drafts that carry the team name instead of the tag
  get the other team of the series (`draft_team_ids`). `team_path` is `teams/<TAG>.png` for the team with the
  most series under a tag and `teams/<team_id_vlr>.png` for the others. `team_economy` PK is
  `team_map_round_id`. Schema change: `sql/team_id_vlr_fase2.sql` + `upload --full`. Tags are still in the
  PKs, so `team_aliases` / `canonical_teams` stay.
- **Unplayed maps** — vlr shows the next map of a series that ended early (map 3 of a 2-0) and maps never
  played (W.O., `TBD`) with an empty round grid and 0 stats. `parsers.game_was_played` (grid present, no
  `rnd-sq mod-win`) drops them from `player_stats_` and from round_detail's map list; before that, an unplayed
  map *before* a played one gave its name to the played map's rounds (787286, 787408, 788432, 788465).
  `tables.drop_unplayed_maps` drops player_stats/performance rows whose `map_id` has no round_detail.
- **New raw columns** — the `save_*` functions append through `save.append_dict_rows`, which rewrites an
  existing csv once (byte-safe, latin-1) adding any column the parser now produces, so a parser can gain a column
  without leaving appended rows misaligned under an old header. Add new columns at the **end** of the parser's
  dict: that keeps existing columns in place and the fixtures diff readable.
- **`map == "all"` rows** are aggregate rows from vlr and must be filtered out before per-map processing.
- **Idempotency** — `csv/scrape_log.csv` (`vlr_pipeline/tracking.py`, mirrored in `vlr_scraper.ipynb` cell 3) has one
  row per match keyed by `series_id` (never the full URL: vlr changes the slug when a `tbd-...` match gets teams)
  with `status` ok/error/skipped, last error, attempts. `linkExtractor` only returns `Completed` cards from the event
  page; `scrape_event` skips ok/skipped (and errors after 3 attempts) without fetching the match. `process_match`
  purges the match's rows from its tournament CSVs before extracting, so retries never duplicate. If the log is
  missing it is bootstrapped from `draft_*.csv` (ok) and legacy `error_match_*.csv` (error).
- **Logs tab** — `get_round_logs` requests `?game=<game_id>&tab=logs` once per played map (each page holds every
  round of that map). `round_buy_` is long (one row per player-round, `slot` = vlr's order); `round_events_` has
  kills/plant/defuse (`pos` = victim/spike, `from` = killer). `table_round_buy` pivots buys to one row per round,
  PK `team_map_round_id` (same `sort_teams` rule as round_info). `table_round_events` (PK `team_map_round_id, ev_index`) and
  `table_round_summary` (per round: first blood, plant, defuse, kills/trades) come from `round_events_` joined to
  round_info on `map_id + round`; trades use a 3 s window (`TRADE_WINDOW`), team kills (spike/fall) are excluded. Matches scraped before this have `has_logs` empty
  in scrape_log: `python -m vlr_pipeline backfill-logs [--limit N] [--tournament X]` fills them without touching
  status/attempts. The Supabase tables are created by hand from `sql/round_buy.sql` and `sql/round_events.sql`.
- **Team tags renamed by vlr** — `round_detail` was scraped months ago, so `round_info` holds the tricode the
  team had back then, while a tab scraped today brings the current one (DRX -> KRX, 6 series of
  `vct_2026_pacific_kickoff`). Every logs table therefore takes `team_map_round_id` **and** `team_a`/`team_b` from
  `round_info` (join on `map_id + round`), never from its own raw tags — what is kept from the raw file is vlr's
  positional order (its team 1 is `teamA` in every tab), which is what makes `player_N_team_a` line up.
  `canonical_teams` (`tables.py`, list in `lookups.py: team_aliases`) rewrites a tag **only when it matches
  neither team of that round**: the rename happened mid-season, so old series legitimately say DRX and new ones
  KRX, and a global replace breaks one or the other. A tag that survives unmapped is logged as a warning by
  `build_round_events` and `build_round_situations` — that is the signal to add it to `team_aliases`.
- **XvY situations** — `table_round_situations` (PK `team_map_round_id, seg_index, team`) has one row per
  (round, segment, team): a segment is a stretch of the round with the alive count already settled. Kills are
  grouped into chained clusters (a kill joins if it is <= `SETTLE_WINDOW` after the previous kill *of the cluster*)
  and the state only counts `SETTLE_WINDOW` s after the cluster's last kill, so a trade never produces a 5v4 that
  was never played; `seg_index` 0 is the opening 5v5. Alive counts come from the **set** of dead players
  (`victim_id_vlr`, nick only as fallback) grouped by `victim_team` (never by the legacy `victim_id`, which carries
  the player's most recent team); team kills count as deaths, and
  vlr does not log resurrects, so those rounds are flagged `has_revive` instead of yielding impossible counts.
  `round_win` always comes from `rndA`/`rndB`: **0 alive does not decide the round** (a wiped team wins if the
  planted spike detonates). Economy comes from `round_buy` (a round-start snapshot) in three sets: `*_start`,
  `*_alive` and `*_rival_alive`. `table_situation_stats` aggregates win rate per tournament/team/side/situation and
  is **not uploaded** (like `table_agent_info`); neither is `round_situations` yet — see `ROADMAP.md`.
- **Economy tab** — since 2026-10 vlr renders it as a div grid (`vlr-rounds-row-col`, `ecc-c`/`ecr-bank` with
  `mod-t1` = team_a); `add_economy_rounds_grid` parses it, the old `mod-econ` table parser stays for old fixture html.
  vlr now rounds the loadout value to 0.1k and shows only 24 rounds (no overtime economy). If `process_match` fails
  midway it purges the rows it already saved, so partial matches never reach the upload.
- **Match format** — an event in `events.json` may carry `"format": "reduced"` (default `full`) for qualifiers
  where vlr has no draft (no bans, no decider map). `scrape_event` writes it to scrape_log's `match_format`
  (and re-syncs already-logged matches with no requests); `build_ids` / `build_region_tournament` read it into
  `table_match_id.match_format` (full/reduced) and `table_tournament.match_format` (full/reduced/mixed). Supabase
  columns come from `sql/match_format.sql`. Reduced matches have no `draft_` rows, so `table_teams` also takes
  teams from `round_detail`. Forfeits (`forfeited by X`) are `skipped` with error `forfeit`, and any rows from an earlier scrape are
  purged (vlr can turn a played match into a forfeit after a disqualification, 784786; the tournament comes from
  `scraper.title_event` because the page has no tricodes). Small teams' logs tab
  can bring the tag in another case (`Rvan` vs `RVAN`). **Team tags are always uppercase in `tables/`**
  (2026-11-07): `upper_tag` runs on every tag column (`TEAM_TAG_COLUMNS`) when raw csv are read
  (`concat_csv_from_different_folders`, round_buy/round_events), so every PK, join and `team_path` uses the
  uppercase tricode while raw `csv/` keeps vlr's case. It decodes the html form first (`MÃ¶rk` -> `MÖRK`).
  `same_team_case` stays as a no-op safety net before `team_aliases` (whose keys must be uppercase).
- **Tournament hierarchy** — `table_tournament` has `year` / `stage` / `subregion` for rviewer's
  Year → Region → Subregion → Tournament filter (`tournament_hierarchy` in `tables.py`, contract in
  `handoff/VLR_SCRAPER_TOURNAMENT_HIERARCHY.md`). They are parsed from `tour_id`; `stage` is a fixed set
  (`STAGE_PATTERNS`), `subregion` only for qualifiers with chip texts from `lookups.subregion_names`. An unknown
  stage goes null and a new subregion goes Title Case, both with a warning — add it and tell rviewer. The csv owns
  these columns (upsert overwrites manual edits), so they must always be computed; empty cells go as NULL
  (`tournament` is in `upload.EMPTY_AS_NULL`).
- **Event end date** — an event may carry `"end_date": "YYYY-MM-DD"`; `config.load_events(only_active=True)` drops it
  once today (UTC) is past `end_date + END_DATE_GRACE_DAYS` (3), even with `"active": true` (`is_active`).
  `events.json` is never rewritten (the bot only commits `csv/`).
- **Event slots** — an event in `events.json` may carry `"slots": N` and `"relevant_teams": [tricodes]` (hand-written,
  in order, at most N; validated in `config.validate_slots`). `build_tournament_slots` writes
  `table_tournament_slots` (PK `tour_id, slot`, `team_id` empty = slot not decided yet), matching the event to its
  `tour_id` by `event_key` (ascii alphanumerics of the url slug vs the tour_id). Supabase table from
  `sql/tournament_slots.sql`. It never writes `teams.relevant`, which rviewer edits by hand.
- **Manual lookup lists** — new maps and agents must be added by hand to the hardcoded lists in
  `csv_process.ipynb` (map_info / agent_path_name), otherwise their rows won't get IDs/images.

## Encoding (recurring source of bugs)

vlr.gg HTML is decoded as `iso-8859-1` (`soup_open(..., decode="iso-8859-1")`). The invariant this creates is
that a non-ASCII nick travels in memory as **its utf-8 bytes reinterpreted as latin-1** ("Rosé" -> "RosÃ©"), so
writing it back with `iso-8859-1` leaves the csv in utf-8 — which is why the readers use utf-8. Anything parsed
from JSON instead of HTML breaks that invariant: `json.loads` returns the nick already decoded, and
`parsers.json_text` exists to put it back into the html form (`get_round_logs` is the only such case today; without
it `table_round_events.csv` stopped being valid utf-8, `upload.read_rows` would have pushed replacement
characters to Supabase and the nick joined neither `round_buy` nor `table_players`). Never call `lower()` /
`upper()` / `strip()` on html-form text: `lower()` turns `Ã` into `ã` and breaks the bytes ("TÃ¼rkiye" became the
`tour_id` `tã¼rkiye`, 2026-11-11), and `strip()` eats a trailing `\x85`/`\xa0` byte (use `parsers.html_text`).
`normalize_filename` and `tournament_hierarchy` decode first; the folder name and scrape_log's `tournament` are
real text (`türkiye`), while `tour_id` in `tables/` is the html form (`json_text` of the folder). CSVs are written with a mix of
`iso-8859-1` and `utf-8` depending on the cell. Notably, `table_round_info.csv` is written with
`encoding="iso-8859-1"` but the resulting bytes are valid utf-8, so it must be **read back as utf-8** for team
names to match other tables. When team names fail to join, suspect an encoding mismatch first.

## Data layout

- `csv/<tournament>/` — raw per-tournament scraper output (one subfolder per event).
- `tables/` — consolidated star-schema output (the deliverable; not in git, uploaded to Supabase).
- New maps/agents must also be added to `vlr_pipeline/lookups.py`, since Actions builds tables with the package.
- `table_players`: one row per `player_id_vlr` (see "Player identity"); nick, `team_id` and the legacy
  `player_id = <team>_<player>` come from the player's most recent match;
  `table_teams` includes draft `team` and `rival`, plus `team_path = teams/<team_id without dots>.png` (logos in
  rviewer; GC tricodes like `GEN.GC` -> `GENGC.png`, `team_id` keeps the dot; see `handoff/SCRAPER_TEAM_PATH.md`). `find_files_by_prefix` sorts files so output doesn't depend on OS
  (os.walk order differs on Linux). Changing a PK-forming rule leaves orphan rows in Supabase (upsert never deletes);
  see `handoff/RKTDATA_CAMBIO_PLAYERS.md` for the 2026-09-14 players change handed off to the rktdata repo.
- `backup/` — archived older tournaments and prior `tables/` snapshots.
- `ROADMAP.md` — done/pending work; update it when finishing or adding a feature.
- `handoff/` — docs exchanged with other repos (rktdata, rviewer, GroupCalculator: contracts, change notices).
  Gitignored on purpose: every new doc of this kind goes there, never at the root or in git.
