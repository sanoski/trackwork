from datetime import date

import pytest

from app import storage, structures


def _line():
    p, _ = storage.create_project("TST", "Test Line", kind="company", line="TST")
    structures.add_location(p, "Yard A")
    return p


def test_switch_update_delete():
    p = _line()
    sw = structures.add_switch(p, "North Main", date(2026, 6, 3),
                               [{"length": 9, "planned": 2, "actual": 3}], location="Yard A")
    assert sw.location == "yard-a"
    sw2 = structures.update_switch(p, sw.id, new_name="North Main Switch", notes="n", location="")
    assert (sw2.name, sw2.notes, sw2.location) == ("North Main Switch", "n", None)
    with pytest.raises(ValueError):
        structures.update_switch(p, sw.id)
    with pytest.raises(LookupError):
        structures.get_entity(p.switches, "nope")
    assert structures.delete_switch(p, sw.id).id == sw.id
    assert p.switches == []


def test_switch_ambiguous_name_needs_date():
    p = _line()
    structures.add_switch(p, "Same", date(2026, 6, 1), [{"length": 9}])
    structures.add_switch(p, "Same", date(2026, 6, 2), [{"length": 9}])
    with pytest.raises(LookupError):
        structures.get_entity(p.switches, "Same")
    assert structures.get_entity(p.switches, "Same", date(2026, 6, 2)).date == date(2026, 6, 2)


def test_derail_update_delete():
    p = _line()
    dr = structures.add_derail(p, "South Derail", date(2026, 6, 4), [], derail_type="portable")
    structures.update_derail(p, dr.id, derail_type="stationary",
                             timbers=[{"length": 12, "planned": 2, "actual": 2, "head_block": True}])
    assert p.derails[0].derail_type == "stationary" and p.derails[0].timbers[0].head_block
    structures.update_derail(p, dr.id, derail_type="")
    assert p.derails[0].derail_type is None
    structures.delete_derail(p, "South Derail")
    assert p.derails == []


def test_location_rules():
    p = _line()
    with pytest.raises(ValueError):
        structures.add_location(p, "yard a")           # duplicate, case-insensitive
    with pytest.raises(ValueError):
        structures.resolve_location(p, "Nowhere")      # managed list
    storage.record_daily_count(p, date(2026, 6, 1), 10, 0, None, "Yard A")
    with pytest.raises(ValueError):
        structures.delete_location(p, "Yard A")        # still referenced
    loc = structures.update_location(p, "Yard A", new_name="Yard B")
    assert loc.id == "yard-a" and loc.name == "Yard B"  # id stays stable on rename
