# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraping + data-processing pipeline for Valorant esports statistics from [vlr.gg](https://www.vlr.gg).
There are no `.py` modules — everything lives in Jupyter notebooks. Output is a star-schema set of CSVs
under `tables/` intended for consumption in Power BI.

Note: `.gitignore` excludes `*.csv` and `*.md`, so scraped data and this file are **not** tracked by git.
Only the notebooks and `requirements.txt` are versioned. Comments/notes in cells are frequently in Spanish.

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
- **Idempotency** — `was_url_already_processed(file_path, url)` guards re-scraping; the scraping driver checks
  `final` status and Bo3/Bo5 before extracting, and writes skips to `error_match_*.csv`.
- **Manual lookup lists** — new maps and agents must be added by hand to the hardcoded lists in
  `csv_process.ipynb` (map_info / agent_path_name), otherwise their rows won't get IDs/images.

## Encoding (recurring source of bugs)

vlr.gg HTML is decoded as `iso-8859-1` (`soup_open(..., decode="iso-8859-1")`). CSVs are written with a mix of
`iso-8859-1` and `utf-8` depending on the cell. Notably, `table_round_info.csv` is written with
`encoding="iso-8859-1"` but the resulting bytes are valid utf-8, so it must be **read back as utf-8** for team
names to match other tables. When team names fail to join, suspect an encoding mismatch first.

## Data layout

- `csv/<tournament>/` — raw per-tournament scraper output (one subfolder per event).
- `tables/` — consolidated star-schema output (the deliverable).
- `backup/` — archived older tournaments and prior `tables/` snapshots.
