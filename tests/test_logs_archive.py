"""logs_archive: push/pull de los csv de logs contra un Supabase Storage falso en memoria."""

import os

import pytest

from vlr_pipeline import logs_archive
from vlr_pipeline.logs_archive import ConflictError, file_states, load_manifest, object_name, pull, push

TOURNAMENT = "vct_2027_emea_kickoff_-_türkiye_qualifier"
KEY = f"{TOURNAMENT}/round_buy_{TOURNAMENT}.csv"
# nick no ascii en forma html (utf-8 leido como latin-1, escrito de nuevo en latin-1 = bytes utf-8)
CONTENT = "series_id,nick,source_url\r\n785988,Rosé,https://www.vlr.gg/785988/x\r\n".encode("utf-8")


class FakeBucket:
    def __init__(self, store, fail=False):
        self.store = store
        self.fail = fail

    def upload(self, path, file, file_options=None):
        if self.fail:
            raise RuntimeError("storage caido")
        self.store[path] = bytes(file)

    def download(self, path, options=None, query_params=None):
        return self.store[path]

    def list(self, path=None, options=None):
        prefix = f"{path}/"
        return [{"name": name[len(prefix):]} for name in sorted(self.store, reverse=True) if name.startswith(prefix)]

    def remove(self, paths):
        for path in paths:
            del self.store[path]


class FakeStorage:
    def __init__(self):
        self.store = {}
        self.fail = False

    def from_(self, bucket):
        assert bucket == logs_archive.BUCKET
        return FakeBucket(self.store, self.fail)


class FakeClient:
    def __init__(self):
        self.storage = FakeStorage()


def write(csv_dir, key, data):
    path = os.path.join(csv_dir, *key.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def copy_manifest(src, dst):
    os.makedirs(dst, exist_ok=True)
    logs_archive.save_manifest(load_manifest(src), dst)


def test_push_then_pull_in_empty_dir_is_byte_identical(tmp_path):
    client = FakeClient()
    local, runner = str(tmp_path / "local"), str(tmp_path / "runner")
    write(local, KEY, CONTENT)
    write(local, f"{TOURNAMENT}/round_detail_{TOURNAMENT}.csv", b"no es de logs")

    assert push(client, local) == 1
    manifest = load_manifest(local)
    assert list(manifest) == [KEY]
    assert manifest[KEY]["object"].isascii()

    copy_manifest(local, runner)  # lo que trae el checkout de git
    assert pull(client, runner) == 1
    with open(os.path.join(runner, *KEY.split("/")), "rb") as f:
        assert f.read() == CONTENT
    assert file_states(runner)[KEY][0] == "ok"
    # segunda corrida: nada que hacer
    assert pull(client, runner) == 0
    assert push(client, runner) == 0


def test_object_name_is_ascii_and_versioned():
    name = object_name(KEY, "ab" * 32)
    assert name == (
        "vct_2027_emea_kickoff_-_turkiye_qualifier/"
        "round_buy_vct_2027_emea_kickoff_-_turkiye_qualifier.abababababab.csv.gz"
    )


def test_states_upload_download_conflict(tmp_path):
    client = FakeClient()
    local, runner = str(tmp_path / "local"), str(tmp_path / "runner")
    write(local, KEY, CONTENT)
    push(client, local)
    copy_manifest(local, runner)
    pull(client, runner)

    # el runner agrega un match y sube: el local queda atrasado
    write(runner, KEY, CONTENT + b"785989,x,https://www.vlr.gg/785989/y\r\n")
    assert file_states(runner)[KEY][0] == "upload"
    push(client, runner)
    copy_manifest(runner, local)  # git pull del manifest nuevo
    assert file_states(local)[KEY][0] == "download"
    assert pull(client, local) == 1
    assert file_states(local)[KEY][0] == "ok"

    # cambian los dos lados: ni pull ni push pisan nada
    write(runner, KEY, CONTENT + b"1,a,https://www.vlr.gg/1/a\r\n")
    push(client, runner)
    copy_manifest(runner, local)
    local_change = CONTENT + b"2,b,https://www.vlr.gg/2/b\r\n"
    path = write(local, KEY, local_change)
    assert file_states(local)[KEY][0] == "conflict"
    with pytest.raises(ConflictError):
        pull(client, local)
    with pytest.raises(ConflictError):
        push(client, local)
    with open(path, "rb") as f:
        assert f.read() == local_change

    # --force en pull: queda la version remota
    pull(client, local, force=True)
    assert file_states(local)[KEY][0] == "ok"


def test_failed_upload_leaves_manifest_untouched(tmp_path):
    client = FakeClient()
    local = str(tmp_path / "local")
    write(local, KEY, CONTENT)
    push(client, local)
    before = load_manifest(local)

    write(local, KEY, CONTENT + b"3,c,https://www.vlr.gg/3/c\r\n")
    client.storage.fail = True
    with pytest.raises(RuntimeError):
        push(client, local)
    assert load_manifest(local) == before
    assert file_states(local)[KEY][0] == "upload"


def test_prune_keeps_current_and_recent(tmp_path):
    client = FakeClient()
    local = str(tmp_path / "local")
    for index in range(4):
        # tamanos distintos: file_sha reusa el sha cacheado si tamano y mtime no cambian
        write(local, KEY, CONTENT + f"{index},{'n' * (index + 1)},https://www.vlr.gg/{index}/n\r\n".encode())
        push(client, local)
    assert len(client.storage.store) == 4

    current = load_manifest(local)[KEY]["object"]
    removed = logs_archive.prune(client, local, keep=2)
    assert len(removed) == 2
    assert current in client.storage.store
    assert len(client.storage.store) == 2
