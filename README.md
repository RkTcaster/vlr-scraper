# vlr-scraper

Scraping and data-processing pipeline for Valorant esports statistics from [vlr.gg](https://www.vlr.gg).

It scrapes every completed match of the events listed in `events.json`, stores the raw data as per-tournament
CSVs, consolidates them into a star schema and upserts it into Supabase Postgres, where
[rktdata.ar](https://rktdata.ar) reads it.

```
vlr.gg ──scrape──> csv/<tournament>/*.csv ──process──> tables/table_*.csv ──upload──> Supabase ──> rktdata.ar
```

A GitHub Actions workflow runs the whole thing once a day and commits the new raw data back to this repo.

## Quick start

CI runs on Python 3.13.

```bash
python -m pip install -r requirements.txt
python -m pip install pytest                 # only for the tests

python -m vlr_pipeline logs pull             # raw logs csv live in Supabase Storage, not in git
python -m vlr_pipeline all --skip-upload     # scrape active events + rebuild tables/
python -m pytest
```

On Windows set `PYTHONIOENCODING=utf-8` first, or non-ASCII team names break in the console.

`logs pull`, `logs push` and `upload` need Supabase credentials: `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
(service role) in the environment, or in a gitignored `.env.local` at the repo root. Without them `all` scrapes
and processes, and skips the upload.

## Commands

Global flags (`--log-level`, `--log-file`) go **before** the subcommand.

| Command | What it does |
| --- | --- |
| `python -m vlr_pipeline scrape` | Scrapes the active events of `events.json` into `csv/` (`--all-events`, `--event-url URL --format reduced`) |
| `python -m vlr_pipeline process` | Rebuilds every `tables/table_*.csv` from `csv/` |
| `python -m vlr_pipeline upload` | Upserts `tables/` into Supabase. Incremental by default; `--full` re-sends everything, `--dry-run` only validates |
| `python -m vlr_pipeline all` | `scrape` + `process` + `upload` (`--skip-upload`, `--full`) |
| `python -m vlr_pipeline backfill-logs` | Adds the logs tab (buys, kills) to matches scraped before it existed |
| `python -m vlr_pipeline logs {status,pull,push,prune,init}` | Syncs the logs csv archive with Supabase Storage |

Day-to-day recipes (in Spanish) are in [COMMANDS.md](COMMANDS.md).

## Configuring events

`events.json` lists the events to scrape. Only `active` ones are scraped by default.

```json
{
  "name": "VCT 2027 EMEA Kickoff Europe Qualifier",
  "url": "https://www.vlr.gg/event/matches/3175/vct-2027-emea-kickoff-europe-qualifier/?series_id=6092",
  "active": true,
  "format": "reduced",
  "end_date": "2026-12-05"
}
```

| Field | Meaning |
| --- | --- |
| `url` | The event's **matches** page on vlr (`/event/matches/<id>/...`) |
| `active` | Scrape it on every run |
| `format` | `full` (default) or `reduced` for qualifiers where vlr has no draft |
| `end_date` | Optional. The event stops being scraped 3 days after this date, even if `active` |
| `slots`, `relevant_teams` | Optional. Qualification slots and the teams holding them (`tournament_slots` table) |

## How it works

**Scrape.** For each event, the completed matches are read from the event page. Each match is one overview
request plus the performance, economy and logs tabs. `csv/scrape_log.csv` keeps one row per match (`series_id`,
status, attempts), so a match already scraped is never requested again, and one that failed is retried up to
three times. A match's rows are purged before it is re-scraped, so retries never duplicate data.

**Process.** `tables/` is rebuilt from scratch on every run, so it is not versioned. Teams and players are
identified by vlr's own ids (`team_id_vlr`, `player_id_vlr`), because tricodes and nicknames repeat across
unrelated teams and players.

**Upload.** Dimension tables are sent in full. Fact tables are sent only for series that are missing from
Supabase or were re-scraped since the last successful upload. `match_id` goes last and only for series whose
facts succeeded, so a failed chunk is retried on the next run. Every run appends to `csv/upload_log.csv`.

### Tables

| Supabase table | Primary key | Content |
| --- | --- | --- |
| `regions`, `tournament` | `reg_id`, `tour_id` | Regions and events, with year / stage / subregion |
| `teams` | `team_id_vlr` | One row per vlr team |
| `players` | `player_id_vlr` | One row per vlr player |
| `tournament_played` | `tour_id, team_id_vlr` | Which teams played which event |
| `tournament_slots` | `tour_id, slot` | Qualification slots per event |
| `maps_name_ids`, `maps_id`, `match_id` | `map_id`, `map_id`, series | Map names, maps played, series |
| `draft` | `series_id` | Picks and bans |
| `round_info` | `team_map_round_id` | Round-by-round result and win condition |
| `team_economy` | `team_map_round_id` | Buy type and bank per round |
| `player_stats` | `map_id, player_id_vlr` | Overview stats per map |
| `player_performance` | `map_id, player_id_vlr` | Multikills, clutches, plants, defuses |
| `round_buy` | `team_map_round_id` | Weapon, shield, spend and bank of all ten players |
| `round_events` | `team_map_round_id, ev_index` | Every kill, plant and defuse with time and position |
| `round_summary` | `team_map_round_id` | First blood, plant, defuse, kills and trades per round |

`table_round_situations` and `table_situation_stats` (XvY man-advantage segments and their win rates) are built
locally and not uploaded yet.

## Automation

`.github/workflows/pipeline.yml` runs daily (cron `0 5 * * *` UTC, always incremental): `logs pull` → `all` →
`logs push` → commit `csv/`. It can also be started by hand, with a `full` input that re-uploads everything.
`.github/workflows/tests.yml` runs the test suite on pushes and pull requests that touch the code, and after each pipeline run.

Since the bot commits to `main` every day, `git pull` before working locally. `csv/` uses a custom merge
driver that merges per series; register it once per clone:

```bash
git config merge.vlr-csv.name "merge de csv/ por serie"
git config merge.vlr-csv.driver "python scripts/merge_csv.py %O %A %B %P"
```

## Repository layout

| Path | Content |
| --- | --- |
| `vlr_pipeline/` | The pipeline package: `scraper`, `parsers`, `save`, `tracking`, `tables`, `lookups`, `upload`, `logs_archive`, `config`, `cli` |
| `scripts/` | One-off and maintenance scripts (backfills, csv merge driver, `relevant_teams.py`, `export_groups.py`) |
| `sql/` | Schema changes and cleanups, applied by hand in the Supabase SQL editor |
| `tests/` | pytest suite; parsers run offline against gzipped html fixtures |
| `csv/` | Raw scraper output, one folder per tournament (versioned) |
| `tables/` | Consolidated output (gitignored, regenerated by `process`) |
| `events.json`, `relevant_teams.json` | Events to scrape; teams flagged as relevant |

The round logs csv (`round_buy_*`, `round_events_*`) are too large for git. They are stored gzipped and
versioned in a private Supabase Storage bucket; `csv/logs_manifest.json` records the current version of each
file. Run `logs pull` before `process` and `logs push` after scraping.

## Maintenance notes

- A new map or agent must be added by hand to `vlr_pipeline/lookups.py`; `tests/test_lookups.py` fails until
  it is.
- After changing table-building code or lookups, run `upload --full`: the incremental upload does not re-send
  matches that are already in Supabase.
- Upserts never delete. Changing how a primary key is formed leaves orphan rows that have to be removed with SQL.
- vlr.gg html is decoded as `iso-8859-1` on purpose. Read the "Encoding" section of [CLAUDE.md](CLAUDE.md)
  before touching anything that handles team or player names.

## More documentation

- [COMMANDS.md](COMMANDS.md): command recipes (Spanish).
- [ROADMAP.md](ROADMAP.md): changelog and pending work (Spanish).
- [CLAUDE.md](CLAUDE.md): architecture conventions and the reasoning behind them.

This project is not affiliated with vlr.gg or Riot Games.
