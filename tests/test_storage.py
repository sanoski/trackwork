from datetime import date

import pytest

from app import storage
from app.config import settings


def test_create_project_single_active_invariant():
    p, demoted = storage.create_project("TST", "Test Line", kind="company", line="TST")
    assert p.project.status == "active" and demoted == []
    _, demoted2 = storage.create_project("S1", "Sponsored", kind="sponsored", goal_ties=1000)
    assert demoted2 == ["TST"]
    assert storage.load_project("TST").project.status == "complete"
    p = storage.load_project("TST")
    assert storage.set_status(p, "active") == ["S1"]
    storage.save_project(p)
    assert storage.load_project("S1").project.status == "complete"


@pytest.mark.parametrize("args", [("bad id!", "x"), ("OK", ""), ("OK", "x", "weird")])
def test_create_project_rejects_bad_input(args):
    with pytest.raises(ValueError):
        storage.create_project(*args)


def test_create_project_rejects_duplicate():
    storage.create_project("TST", "x")
    with pytest.raises(ValueError):
        storage.create_project("TST", "y")


def test_legacy_kind_alias():
    p, _ = storage.create_project("L", "Line", kind="line")
    assert p.project.kind == "company"


def test_update_meta_recalculates_and_archives():
    p, _ = storage.create_project("TST", "Test Line")
    storage.record_daily_count(p, date(2026, 6, 1), 100)
    storage.record_daily_count(p, date(2026, 6, 2), 50)
    storage.update_project_meta(p, daily_target=60, goal_ties=1000)
    assert [e.vs_target for e in p.daily_log] == [40, -10]
    assert [e.remaining for e in p.daily_log] == [900, 850]
    with pytest.raises(ValueError):
        storage.update_project_meta(p)
    with pytest.raises(ValueError):
        storage.update_project_meta(p, bogus=1)
    with pytest.raises(ValueError):
        storage.set_status(p, "gone")
    storage.set_status(p, "archived")
    storage.save_project(p)
    assert (settings.archived_dir / "TST.json").exists()
    assert not (settings.projects_dir / "TST.json").exists()


def test_json_documents_roundtrip():
    path = settings.settings_file
    assert storage.load_json(path, {"x": 1}) == {"x": 1}
    storage.save_json(path, {"a": [1, 2], "b": {"c": None}})
    assert storage.load_json(path) == {"a": [1, 2], "b": {"c": None}}
