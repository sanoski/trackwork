from datetime import date

import pytest

from app import downtime, storage


def _p():
    p, _ = storage.create_project("TST", "Test Line")
    return p


def test_calc_duration():
    assert downtime.calc_duration("08:00", "09:30") == 90
    assert downtime.calc_duration("10:00", "09:00") is None
    assert downtime.calc_duration(None, "09:00") is None
    assert downtime.calc_duration("bad", "09:00") is None


def test_add_update_delete_and_ambiguity():
    p = _p()
    e = downtime.add_downtime(p, date(2026, 6, 5), "Tamper", "08:00", "09:30", "leak")
    assert e.duration_minutes == 90
    downtime.add_downtime(p, date(2026, 6, 5), "Tamper", "13:00")
    with pytest.raises(ValueError):
        downtime.update_downtime(p, date(2026, 6, 5), "Tamper", notes="x")      # ambiguous
    e2 = downtime.update_downtime(p, date(2026, 6, 5), "Tamper", resumed="14:00", match_down_at="13:00")
    assert e2.duration_minutes == 60
    with pytest.raises(ValueError):
        downtime.update_downtime(p, date(2026, 6, 5), "Tamper", match_down_at="13:00")   # no fields
    with pytest.raises(ValueError):
        downtime.add_downtime(p, date(2026, 6, 5), "  ")                          # blank machine
    downtime.delete_downtime(p, date(2026, 6, 5), "Tamper", "08:00")
    assert len(p.equipment_downtime) == 1
    with pytest.raises(LookupError):
        downtime.find_downtime(p, date(2026, 6, 9), "Tamper")
    with pytest.raises(LookupError):
        downtime.find_downtime(p, date(2026, 6, 5), "Tamper", "07:00")
