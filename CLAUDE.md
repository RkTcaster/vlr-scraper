# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraping + data-processing pipeline for Valorant esports statistics from [vlr.gg](https://www.vlr.gg).
Output is a star-schema set of CSVs under `tables/` that is upserted into Supabase Postgres tables
(`vlr_pipeline/upload.py`, port of rktdata's `scripts/upload.mjs`: file → table → PK list) and consumed by rktdata.ar.
Every upload run appends one row per table to `csv/upload_log.csv` (rows, failed_rows, status, last error, GitHub run id). Logic exists twice and must be kept in sync: the notebooks (`vlr_scraper.ipynb`,
`csv_process.ipynb`) and the headless package `vlr_pipeline/` (`python -m vlr_pipeline [--log-level X] {scrape,process,upload,all}`;
global flags go before the subcommand).

Production runs in GitHub Actions (`.github/workflows/pipeline.yml`, daily 06:00 UTC): scrapes the `active` events in
`events.json`, rebuilds `tables/`, uploads to Supabase, and commits only `csv/` back to the repo. `csv/` (including
`csv/scrape_log.csv`) is versioned; `tables/` is gitignored because it is fully regenerated from `csv/` (the package
output was verified byte-identical to the notebook's). `.gitattributes` keeps `*.csv` line endings untouched.
Pull before running notebooks locally to avoid conflicts with the bot's commits. Comments are frequently in Spanish.

## Environment & running

- Conda env on Python 3.11 (win-64). `requirements.txt` is a conda spec, not pip:
  `conda create --name <env> --file requirements.txt`
- Core stack: `beautifulsoup4` + `urllib` (scraping), `pandas`/`numpy` (processing), `matplotlib`, `scikit-learn`.
- Run notebooks in Jupyter, or execute headless:
  `jupyter nbconvert --to notebook --execute --inplace vlr_scraper.ipynb`
- Some cells need `PYTHONIOENCODING=utf-8` set (Windows console default mangles non-ASCII team names).

## Notebook roles

- **`vlr_scraper.ipynb`** — the current/canonical scraper. Cells 1–2 define all functions; later cells
  are interactive scratch/testing against a single hardcoded match `url`. Per-tournament CSVs are written to
  `csv/<normalized_tournament>/` with prefixes: `draft_`, `player_stats_`, `player_performance_`,
  `round_detail_`, `team_economy_`, `error_match_`.
- **`csv_process.ipynb`** — consolidation pipeline. `concat_csv_from_different_folders(folder, prefix)` reads
  every per-tournament CSV with a given prefix across `csv/*/`, then builds the dimension/fact tables in
  `tables/table_*.csv` (region, tournament, teams, players, maps, round info, economy, drafts, performance).
  Also exports group `standings.csv` / `h2h.csv` (see the INPUT_CONTRACT cells near the end).
- **`Webscraper.ipynb`** — legacy/older version of both the scraper and the downstream pipeline. Uses flat,
  hardcoded filenames (`picks.csv`, `Statsamer1.csv`, `bo5amer1.csv`) and lots of hardcoded region/tournament
  wiring. Prefer `vlr_scraper.ipynb` + `csv_process.ipynb`; keep this only as reference.
- **`round_process.ipynb`** — analysis/exploration of economy buys and round-by-round comeback detection.

## Architecture conventions (read before editing extractors)

- **`basic_match_info`** — a dict produced by `get_basic_match_info(soup, url)` and threaded through every
  extractor and save function. It is the single source of match context (teams, event, date, source_url, bo).
- **ID scheme** — `series_id` is parsed from the match URL via `re.search(r"vlr\.gg/(\d+)", url)`;
  `map_id = f"{series_id}-{map}"`. Joins across tables rely on these. Region/tournament IDs (`reg_*`, `tour_id`)
  are assigned from the normalized tournament folder name.
- **`map == "all"` rows** are aggregate rows from vlr and must be filtered out before per-map processing.
- **Idempotency** — `csv/scrape_log.csv` (`vlr_pipeline/tracking.py`, mirrored in `vlr_scraper.ipynb` cell 3) has one
  row per match keyed by `series_id` (never the full URL: vlr changes the slug when a `tbd-...` match gets teams)
  with `status` ok/error/skipped, last error, attempts. `linkExtractor` only returns `Completed` cards from the event
  page; `scrape_event` skips ok/skipped (and errors after 3 attempts) without fetching the match. `process_match`
  purges the match's rows from its tournament CSVs before extracting, so retries never duplicate. If the log is
  missing it is bootstrapped from `draft_*.csv` (ok) and legacy `error_match_*.csv` (error).
- **Manual lookup lists** — new maps and agents must be added by hand to the hardcoded lists in
  `csv_process.ipynb` (map_info / agent_path_name), otherwise their rows won't get IDs/images.

## Encoding (recurring source of bugs)

vlr.gg HTML is decoded as `iso-8859-1` (`soup_open(..., decode="iso-8859-1")`). CSVs are written with a mix of
`iso-8859-1` and `utf-8` depending on the cell. Notably, `table_round_info.csv` is written with
`encoding="iso-8859-1"` but the resulting bytes are valid utf-8, so it must be **read back as utf-8** for team
names to match other tables. When team names fail to join, suspect an encoding mismatch first.

## Data layout

- `csv/<tournament>/` — raw per-tournament scraper output (one subfolder per event).
- `tables/` — consolidated star-schema output (the deliverable; not in git, uploaded to Supabase).
- New maps/agents must also be added to `vlr_pipeline/lookups.py`, since Actions builds tables with the package.
- `table_players`: one row per nick, `player_id = <team>_<player>` with the team of the player's most recent match;
  `table_teams` includes draft `team` and `rival`. `find_files_by_prefix` sorts files so output doesn't depend on OS
  (os.walk order differs on Linux). Changing a PK-forming rule leaves orphan rows in Supabase (upsert never deletes);
  see `RKTDATA_CAMBIO_PLAYERS.md` for the 2026-09-14 players change handed off to the rktdata repo.
- `backup/` — archived older tournaments and prior `tables/` snapshots.
