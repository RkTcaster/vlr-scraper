"""Ingesta de GRID (vlr_pipeline/grid.py), offline: un transport falso reemplaza a la API."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from vlr_pipeline import grid

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    """Devuelve las respuestas en orden y guarda cada request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        status, body = self.responses.pop(0)
        return status, body if isinstance(body, str) else json.dumps(body)


def make_client(*responses):
    transport = FakeTransport(*responses)
    sleeps = []
    client = grid.GridClient("key", transport=transport, sleep=sleeps.append, clock=lambda: 0.0)
    return client, transport, sleeps


def node(sid, start="2026-11-01T18:00:00Z", updated="2026-11-01T22:00:00Z", tournament="VCT EMEA - Stage 2"):
    return {"id": sid, "startTimeScheduled": start, "updatedAt": updated, "tournament": {"name": tournament}}


def page(nodes, has_next=False, cursor="c1"):
    return {"data": {"allSeries": {"totalCount": len(nodes), "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                                   "edges": [{"node": n} for n in nodes]}}}


# --- cliente ------------------------------------------------------------------------------------------------

def test_api_key_goes_in_header_and_is_required():
    client, transport, _ = make_client((200, {"data": {"titles": []}}))
    client.query(grid.CENTRAL_URL, "query { titles { id } }")
    assert transport.calls[0][2]["x-api-key"] == "key"
    with pytest.raises(grid.GridError):
        grid.GridClient("")


def test_rate_limit_comes_as_graphql_error_and_is_retried():
    # GRID avisa el rate limit con HTTP 200 + errors, no con 429
    limited = (200, {"errors": [{"message": "You have exceeded your rate limit, please try again later"}]})
    client, transport, sleeps = make_client(limited, (200, {"data": {"ok": 1}}))
    assert client.query(grid.STATE_URL, "q") == {"ok": 1}
    assert len(transport.calls) == 2
    assert grid.RATE_LIMIT_WAIT in sleeps


def test_other_graphql_errors_are_not_retried():
    client, transport, _ = make_client((200, {"errors": [{"message": "Requested field is only available from version 3.50"}]}))
    with pytest.raises(grid.GridError, match="3.50"):
        client.query(grid.STATE_URL, "q")
    assert len(transport.calls) == 1


def test_http_5xx_is_retried_and_401_is_not():
    client, transport, _ = make_client((503, "down"), (200, {"data": {}}))
    assert client.query(grid.STATE_URL, "q") == {}
    client, transport, _ = make_client((401, "nope"))
    with pytest.raises(grid.GridError, match="401"):
        client.query(grid.STATE_URL, "q")


def test_requests_are_spaced_per_endpoint():
    sleeps = []
    # primera llamada: marca t=0; segunda: a t=1 todavia falta MIN_INTERVAL - 1
    times = iter([0.0, 1.0, 1.0])
    transport = FakeTransport((200, {"data": {}}), (200, {"data": {}}))
    client = grid.GridClient("key", transport=transport, sleep=sleeps.append, clock=lambda: next(times))
    client.query(grid.CENTRAL_URL, "q")
    client.query(grid.CENTRAL_URL, "q")
    assert sleeps == [pytest.approx(grid.MIN_INTERVAL[grid.CENTRAL_URL] - 1.0)]


# --- catalogo -----------------------------------------------------------------------------------------------

def test_catalog_paginates_and_skips_test_series(tmp_path):
    client, transport, _ = make_client(
        (200, page([node("1"), node("6", tournament="GRID-TEST")], has_next=True, cursor="A")),
        (200, page([node("2")])),
    )
    total, changed = grid.sync_catalog(client, grid_dir=str(tmp_path), since="2026-01-01")
    assert (total, changed) == (2, 2)
    assert transport.calls[1][1]["variables"]["after"] == "A"
    flt = transport.calls[0][1]["variables"]["filter"]
    assert flt["titleId"] == "6" and flt["types"] == ["ESPORTS"] and "updatedAt" not in flt
    ids = [row["id"] for row in grid.read_jsonl(str(tmp_path / grid.CATALOG_FILE))]
    assert ids == ["1", "2"]


def test_second_catalog_sync_only_asks_for_updated_series_and_merges(tmp_path):
    client, _, _ = make_client((200, page([node("1"), node("2")])))
    grid.sync_catalog(client, grid_dir=str(tmp_path), since="2026-01-01")

    changed_2 = node("2", updated="2026-11-19T10:00:00Z")
    client, transport, _ = make_client((200, page([changed_2, node("3")])))
    total, changed = grid.sync_catalog(client, grid_dir=str(tmp_path), since="2026-01-01")
    assert (total, changed) == (3, 2)
    assert "updatedAt" in transport.calls[0][1]["variables"]["filter"]
    rows = {row["id"]: row for row in grid.read_jsonl(str(tmp_path / grid.CATALOG_FILE))}
    assert rows["2"]["updatedAt"] == "2026-11-19T10:00:00Z" and "1" in rows


def test_catalog_with_another_since_is_rebuilt(tmp_path):
    client, _, _ = make_client((200, page([node("1")])))
    grid.sync_catalog(client, grid_dir=str(tmp_path), since="2026-06-01")
    client, transport, _ = make_client((200, page([node("2")])))
    grid.sync_catalog(client, grid_dir=str(tmp_path), since="2026-01-01")
    assert "updatedAt" not in transport.calls[0][1]["variables"]["filter"]


# --- series state -------------------------------------------------------------------------------------------

def saved(fetched_at, finished=True):
    return {"fetched_at": fetched_at, "state": {"finished": finished}}


@pytest.mark.parametrize("n, s, expected", [
    (node("1", start="2026-11-20T18:00:00Z"), None, None),                       # todavia no se juega
    (node("1"), None, "nueva"),
    (node("1"), saved("2026-11-01T20:00:00Z", finished=False), "sin terminar"),
    (node("1", updated="2026-11-10T00:00:00Z"), saved("2026-11-09T00:00:00Z"), "modificada en GRID"),
    (node("1"), saved("2026-11-02T00:00:00Z"), f"bajada antes de {grid.REFRESH_DAYS} dias"),
    (node("1"), saved("2026-11-09T00:00:00Z"), None),                            # ya esta firme
])
def test_needs_state(n, s, expected):
    assert grid.needs_state(n, s, NOW) == expected


def test_sync_states_writes_gzip_and_tolerates_missing_series_state(tmp_path):
    grid.write_jsonl(str(tmp_path / grid.CATALOG_FILE), [node("1"), node("2")])
    state = {"id": "1", "finished": True, "games": []}
    # GRID omite los null: una serie sin estado llega como data sin la clave seriesState
    client, _, _ = make_client((200, {"data": {"seriesState": state}}), (200, {"data": {}}))
    counts = grid.sync_states(client, grid_dir=str(tmp_path), now=NOW)
    assert counts == {"ok": 1, "sin_estado": 1, "error": 0}
    stored = grid.read_json(grid.state_path(str(tmp_path), "1"))
    assert stored["state"] == state and stored["series_id"] == "1"
    assert grid.state_path(str(tmp_path), "1").endswith(".json.gz")


def test_sync_states_skips_settled_series_and_counts_errors(tmp_path):
    grid.write_jsonl(str(tmp_path / grid.CATALOG_FILE), [node("1"), node("2")])
    (tmp_path / grid.STATE_DIR).mkdir()
    grid.write_json(grid.state_path(str(tmp_path), "1"), saved("2026-11-09T00:00:00Z"))
    client, transport, _ = make_client((200, {"errors": [{"message": "boom"}]}))
    counts = grid.sync_states(client, grid_dir=str(tmp_path), now=NOW)
    assert counts == {"ok": 0, "sin_estado": 0, "error": 1}
    assert len(transport.calls) == 1  # la serie 1 ya estaba firme


def test_gzip_output_is_deterministic(tmp_path):
    path = str(tmp_path / "x.json.gz")
    grid.write_json(path, {"b": 1, "a": "Rosé"})
    first = open(path, "rb").read()
    grid.write_json(path, {"a": "Rosé", "b": 1})
    assert open(path, "rb").read() == first
    assert grid.read_json(path) == {"a": "Rosé", "b": 1}


def test_cli_grid_returns_1_on_state_errors(monkeypatch, tmp_path):
    from vlr_pipeline.cli import main

    monkeypatch.setattr(grid, "client_from_env", lambda: object())
    monkeypatch.setattr(grid, "sync_states", lambda client, **kw: {"ok": 0, "sin_estado": 0, "error": 2})
    assert main(["grid", "states", "--grid-dir", str(tmp_path)]) == 1
