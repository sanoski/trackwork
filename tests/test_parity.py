"""Three ways in, one source of truth: every MCP tool has a CLI twin (and, from the web parity
phase, a web route). The mapping is explicit so a new tool without its twin fails here."""
import argparse
import asyncio
import importlib
import importlib.util
import inspect
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# MCP tool -> CLI subcommand
TWINS = {
    "list_projects": "list", "get_project_summary": "summary", "get_daily_log": "log",
    "get_downtime_log": "downtime", "get_switches": "switches", "get_derails": "derails",
    "get_locations": "locations",
    "add_daily_count": "add-count", "update_daily_count": "update-count",
    "add_downtime": "add-downtime", "update_downtime": "update-downtime", "delete_downtime": "delete-downtime",
    "add_switch": "add-switch", "update_switch": "update-switch", "delete_switch": "delete-switch",
    "add_derail": "add-derail", "update_derail": "update-derail", "delete_derail": "delete-derail",
    "add_location": "add-location", "update_location": "update-location", "delete_location": "delete-location",
    "create_project": "create", "update_project": "update", "set_status": "set-status",
}


def mcp_tool_names() -> set[str]:
    server = importlib.import_module("mcp_server.server")
    tools = server.mcp.list_tools()          # FastMCP 3.x: async, returns tool objects
    if inspect.isawaitable(tools):
        tools = asyncio.run(tools)
    return {getattr(t, "name", t) for t in tools}


def cli_commands() -> set[str]:
    spec = importlib.util.spec_from_file_location("trackwork_cli", ROOT / "scripts" / "cli.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    parser = cli.build_parser()
    subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    return set(subs[0].choices.keys())


def test_every_mcp_tool_is_in_the_twin_table():
    assert mcp_tool_names() == set(TWINS), "add the new tool (and its CLI twin) to TWINS"


def test_every_twin_exists_in_the_cli():
    missing = set(TWINS.values()) - cli_commands()
    assert not missing, f"CLI is missing twins: {sorted(missing)}"


def test_cli_extras_are_the_documented_ones():
    extras = cli_commands() - set(TWINS.values())
    assert extras == {"archive", "export", "report", "user", "settings", "schedule", "import", "verify", "token"}


# MCP tool -> (method, web route). Reads map to the whole-project GET, which carries every list.
ROUTES = {
    "list_projects": ("GET", "/api/projects"),
    "get_project_summary": ("GET", "/api/projects/{project_id}/summary"),
    "get_daily_log": ("GET", "/api/projects/{project_id}"),
    "get_downtime_log": ("GET", "/api/projects/{project_id}"),
    "get_switches": ("GET", "/api/projects/{project_id}"),
    "get_derails": ("GET", "/api/projects/{project_id}"),
    "get_locations": ("GET", "/api/projects/{project_id}"),
    "add_daily_count": ("POST", "/api/projects/{project_id}/log"),
    "update_daily_count": ("PATCH", "/api/projects/{project_id}/log/{entry_date}"),
    "add_downtime": ("POST", "/api/projects/{project_id}/downtime"),
    "update_downtime": ("PATCH", "/api/projects/{project_id}/downtime/{entry_date}"),
    "delete_downtime": ("DELETE", "/api/projects/{project_id}/downtime/{entry_date}"),
    "add_switch": ("POST", "/api/projects/{project_id}/switches"),
    "update_switch": ("PATCH", "/api/projects/{project_id}/switches/{switch_id}"),
    "delete_switch": ("DELETE", "/api/projects/{project_id}/switches/{switch_id}"),
    "add_derail": ("POST", "/api/projects/{project_id}/derails"),
    "update_derail": ("PATCH", "/api/projects/{project_id}/derails/{derail_id}"),
    "delete_derail": ("DELETE", "/api/projects/{project_id}/derails/{derail_id}"),
    "add_location": ("POST", "/api/projects/{project_id}/locations"),
    "update_location": ("PATCH", "/api/projects/{project_id}/locations/{location_id}"),
    "delete_location": ("DELETE", "/api/projects/{project_id}/locations/{location_id}"),
    "create_project": ("POST", "/api/projects"),
    "update_project": ("PATCH", "/api/projects/{project_id}"),
    "set_status": ("POST", "/api/projects/{project_id}/status"),
}


def web_routes() -> set[tuple[str, str]]:
    """Every (METHOD, path) the app exposes, read from its OpenAPI schema so this does not
    depend on how a given FastAPI version nests included routers."""
    from app.main import app
    paths = app.openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


def test_every_mcp_tool_has_a_web_route():
    assert set(ROUTES) == set(TWINS), "keep ROUTES and TWINS in step"
    have = web_routes()
    missing = {tool: spec for tool, spec in ROUTES.items() if spec not in have}
    assert not missing, f"web is missing routes: {missing}"
