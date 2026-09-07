"""`cli import`: a data bundle lands in DATA_DIR, and --replace clears whatever was there first
(the demo dataset must never linger beside real data, or two projects end up active)."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
from app import storage, users  # noqa: E402


def _bundle(tmp_path, pid, name):
    b = tmp_path / f"bundle-{pid}"
    (b / "projects").mkdir(parents=True)
    # a real project file as the template, so the loader accepts it
    demo_file = pathlib.Path(__file__).resolve().parents[1] / "demo" / "data" / "projects" / "NVR_ND.json"
    proj = json.loads(demo_file.read_text())
    proj["project"].update({"id": pid, "name": name, "line": pid})
    (b / "projects" / f"{pid}.json").write_text(json.dumps(proj))
    (b / "config.json").write_text(json.dumps({"equipment": ["Tamper"]}))
    return b


def test_import_replace_clears_old_projects(tmp_path, capsys):
    users.create_user("admin@example.com", "Admin", "password123", "admin")
    parser = cli.build_parser()

    demo = _bundle(tmp_path, "DEMO", "Demo Line")
    cli.cmd_import(parser.parse_args(["import", str(demo), "--overwrite"]))
    assert {p.project.id for p in storage.list_projects()} == {"DEMO"}

    real = _bundle(tmp_path, "REAL", "Real Line")
    cli.cmd_import(parser.parse_args(["import", str(real), "--overwrite"]))
    assert {p.project.id for p in storage.list_projects()} == {"DEMO", "REAL"}   # plain import adds

    cli.cmd_import(parser.parse_args(["import", str(real), "--overwrite", "--replace"]))
    assert {p.project.id for p in storage.list_projects()} == {"REAL"}           # --replace clears
    assert [u.email for u in users.list_users()] == ["admin@example.com"]        # accounts untouched
    assert "Removed" in capsys.readouterr().out
